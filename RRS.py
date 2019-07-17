import os
import re
import time
import json
import kivy
import random
import pickle
import threading
import webbrowser
import subprocess
from functools import partial
from datetime import datetime, timedelta
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.lang.builder import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.properties import DictProperty,  ListProperty, StringProperty, ObjectProperty

Builder.load_string("""
<ResourcePopup>
    text: 'Resource settings'
    size_hint: [0.4,0.4]
    auto_dismiss: False
    project: projectText
    cpus: cpuText
    memory: memText
    duration: timeText
    pos_hint: {'center_x':0.5, 'center_y':0.5}
    GridLayout:
        cols: 2
        Label:
            text: "Project"
        TextInput:
            id: projectText
        Label:
            text: "Cpus (number)"
        TextInput:
            id: cpuText
            hint_text: "1"
        Label:
            text: "Memory (GB)"
        TextInput:
            id: memText
            hint_text: "8"
        Label:
            text: 'Time (hours)'
        TextInput:
            id: timeText
            hint_text: "1"
        Button:
            text: 'confirm'
            on_press: root.closeAndStart()
        Button:
            text: 'cancel'
            on_press: root.dismiss()

<ConfigPopup>
    text: 'Settings'
    size_hint: [0.6,0.4]
    auto_dismiss: False
    projectPath: projectPathText
    host: hostText
    imgName: imgNameText
    pos_hint: {'center_x':0.5, 'center_y':0.5}
    GridLayout:
        cols: 2
        Label:
            text: "Path to project folders"
        TextInput:
            id: projectPathText
            hint_text: root.currProjectPath
        Label:
            text: "Name of the hpc host"
        TextInput:
            id: hostText
            hint_text: root.currHost
        Label:
            text: "Singularity image name"
        TextInput:
            id: imgNameText
            hint_text: root.currImgName
        Button:
            text: 'confirm'
            on_press: root.closeAndStart()
        Button:
            text: 'cancel'
            on_press: root.dismiss()
<RootWidget>
    id: rootwid
    logOutputLabel: logOutputLabel
    BoxLayout:
        id: box
        orientation: 'vertical'
        Label:
            id: connectionText
            size_hint: 1, 0.4
            text: "YOU ARE NOT CONNECTED"
        GridLayout:
            cols: 5
            size_hint: 1, 0.3
            Button:
                id: browser
                text: 'Open in browser'
                on_press: joblist.startThread(joblist.openBrowser)
            Button:
                id: connect
                text: 'Reconnect to jobs'
                on_press: joblist.startThread(joblist.reconnectAll)
            Button:
                id: new_job
                text: 'new job'
                on_press:
                    joblist.resPop.open()
            Button:
                id: kill_job
                text: 'kill job'
                on_press: joblist.startThread(joblist.deleteJob)
            Button:
                id: config
                size_hint: 0.3, 0.3
                text: 'settings'
                on_press: joblist.confOpen.open()
        Label:
            size_hint: 1, 0.1
            text: 'Running Jobs'
        JobList:
            id: joblist
            logOutput: root.logOutputLabel
            cols: 1
            size_hint: 1, 0.5
        Label:
            size_hint: 1, 0.1
            text: 'Log Output'
        TestScroll:
            LogOutput:
                id: logOutputLabel
                text: ''
                font_size: 30
                text_size: self.width, None
                size_hint_y: None
                height: self.texture_size[1]
                multiline: True
""")


class ResourcePopup(Popup):
    """"""
    project = ObjectProperty(None)
    cpus = ObjectProperty(None)
    memory = ObjectProperty(None)
    duration = ObjectProperty(None)

    #----------------------------------------------------------------------
    def __init__(self, jobList, **kwargs):
        """Constructor"""
        super(ResourcePopup, self).__init__(**kwargs)
        self.title = 'Required Resources'
        self.joblist = jobList

    #----------------------------------------------------------------------
    def closeAndStart(self):
        """"""
        self.joblist.startThread(self.joblist.submitJob,
                                 self.project.text,
                                 self.cpus.text,
                                 self.memory.text,
                                 self.duration.text)
        self.dismiss()

#----------------------------------------------------------------------
def readConfig():
    """read config file from home"""
    configPath = os.path.expanduser("~/.RRS_config")
    if os.path.isfile(configPath):
        confDict = json.load(open(configPath))

        return confDict
    else:
        defaultSSHHost = 'hpc'
        defaultProjectPath = '/hpc/pmc_gen/rstudio/'
        defaultImg = 'rstudio.simg'
        confDict = {'host': defaultSSHHost,
                    'projectPath': defaultProjectPath,
                    'imgName': defaultImg,}

        return confDict

class ConfigPopup(Popup):
    """"""

    projectPath = ObjectProperty(None)
    host = ObjectProperty(None)
    imgName = ObjectProperty(None)

    currConfig = readConfig()
    currProjectPath = StringProperty(currConfig['projectPath'])
    currHost = StringProperty(currConfig['host'])
    currImgName = StringProperty(currConfig['imgName'])

    #----------------------------------------------------------------------
    def __init__(self, jobList, configDict, **kwargs):
        """Constructor"""
        super(ConfigPopup, self).__init__(**kwargs)
        self.title = 'Settings'
        self.joblist = jobList
    #----------------------------------------------------------------------
    def closeAndStart(self):
        """"""

        currConfigDict = self.currConfig
        newConfigDict = {'host': self.host.text,
                         'projectPath': self.projectPath.text,
                         'imgName': self.imgName.text,}
        if newConfigDict['host'] and not self.joblist.checkHPCConnection(newConfigDict['host']):
            textLog = self.joblist.getLogFunction()
            newHost = newConfigDict['host']
            textLog(f'the SSH host you tried to set ({newHost}) does not appear to connect correctly '
                    f'Is the host name spelled correctly? does the host allow passwordless connection? '
                    f'(test with ssh <hostname> to check if passwordless login is possible) ')
            self.host.text = ''
            self.dismiss()
            return True

        for i in currConfigDict:
            if newConfigDict[i]:
                currConfigDict[i] = newConfigDict[i]


        self.joblist.configDict = currConfigDict
        self.joblist.saveConfig()
        self.dismiss()

class LogOutput(Label):
    """"""

    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
        """Constructor"""
        super(LogOutput, self).__init__(**kwargs)

    #----------------------------------------------------------------------
    def logText(self, value):
        """"""
        currentTime = str(datetime.now().time()).split('.')[0]
        if not value.endswith("\n"):
            value = value + '\n'
        self.text = currentTime + ": " + value + self.text



class TestScroll(ScrollView):
    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
        """Constructor"""
        super(TestScroll, self).__init__(**kwargs)



class JobList(GridLayout):
    """"""
    runningJobs = DictProperty({}) # {jobnumber: [port, stopTime, nodeID, name]}
    currentButtons = {}
    connectionButtonIndex = 4
    currentConnection = DictProperty({})
    configDict = readConfig()
    logOutput = ObjectProperty(None)
    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
        """Constructor"""
        super(JobList, self).__init__(**kwargs)
        self.selectedJob = ''
        self.resPop = ResourcePopup(self)
        self.confOpen = ConfigPopup(self, self.configDict)
        self.startThread(self.startup)


    #----------------------------------------------------------------------
    def startup(self, ):
        """"""
        time.sleep(0.5)
        logText = self.getLogFunction()
        logText('checking connection and loading running jobs if present...')

        userHomePath = os.path.expanduser("~/")
        if os.path.isfile(userHomePath + '.jobs.pkl'):
            loadedRunningJobs = pickle.load(open(userHomePath + '.jobs.pkl', 'rb'))
            if self.checkHPCConnection():
                self.runningJobs =  self.checkJobs(loadedRunningJobs)
                logText('Done!')
            else:
                self.runningJobs = {}
                self.nonFunctionalSSH()
            if self.runningJobs:
                self.reconnectAll()



    #----------------------------------------------------------------------
    def nonFunctionalSSH(self, *args):
        """"""
        textLog = self.getLogFunction()
        host = self.configDict['host']
        textLog(f'The SSH host specified ({host}) does not allow connection to the hpc. '
                f'Is the host name spelled correctly? does the host allow passwordless connection? '
                f'(test with ssh <hostname> to check if passwordless login is possible) '
                f'You can change the default SSH host using the settings button.')
    #----------------------------------------------------------------------
    def checkHPCConnection(self, host = ''):
        """"""
        check = self.sshCommand('echo gooby', host)
        return check

    #----------------------------------------------------------------------
    def saveConfig(self):
        """"""
        logText = self.getLogFunction()
        logText('saving configuration...')
        configFile = os.path.expanduser("~/.RRS_config")
        json.dump(self.configDict, open(configFile, 'w'))
        logText("saved!")

    #----------------------------------------------------------------------
    def openBrowser(self):
        """"""
        selectedJobN = self.getSelectedJob()
        if selectedJobN:
            port = self.runningJobs[selectedJobN][0]
            url = f'http://localhost:{port}'
            webbrowser.open_new_tab(url)

    #----------------------------------------------------------------------
    def countDown(self, pls):
        """"""
        if not self.runningJobs:
            return False


        for i in list(self.runningJobs.keys()):
            project = self.runningJobs[i][3]
            endTime = self.runningJobs[i][1]
            delta = endTime - datetime.now()
            deltaReadable = str(delta).split('.')[0]
            self.currentButtons[i].text = str("job for project " + str(project) +
                                              "  will stop in: " + deltaReadable)
            if deltaReadable == '0:00:01':
                textLog = self.getLogFunction()
                textLog(f'{project} job with number {i} has expired and will be closed.')
                if self.currentConnection[i]:
                    self.currentConnection[i][0].kill()
                del self.runningJobs[i]
                del self.currentConnection[i]
        return True

    #----------------------------------------------------------------------
    def checkJobs(self, loadedRunningJobs):
        """"""

        qstatTable = self.qstat()
        if qstatTable:
            keys = loadedRunningJobs.keys()
            for i in list(keys):
                if i not in qstatTable:
                    del loadedRunningJobs[i]
            return loadedRunningJobs
        else:
            return {}

    #----------------------------------------------------------------------
    def drawButtons(self):
        """"""

        for i in self.runningJobs:
            job = self.runningJobs[i]
            but = Button()
            if i not in self.currentButtons:
                self.currentButtons[i] = but

            but.bind(on_press = partial(self.selectStuff, i))  #shohuld be moved to kv file
            self.add_widget(but)
        Clock.schedule_interval(self.countDown, 1)

    #----------------------------------------------------------------------
    def removeButtons(self):
        """"""
        for i in self.currentButtons.keys():
            self.remove_widget(self.currentButtons[i])
        self.currentButtons = {}

    #----------------------------------------------------------------------
    def on_runningJobs(self, instance, value):
        """"""
        self.removeButtons()
        self.drawButtons()

    #----------------------------------------------------------------------
    def selectStuff(self, key, instance):
        """"""
        self.selectedJob = key
        print(self.selectedJob)
        instance.background_color = (0.5, 1, 0.2, 1)

        for i in self.currentButtons:
            if i == key:
                continue
            btn = self.currentButtons[i]
            btn.background_color = (1, 1, 1, 1)

    #----------------------------------------------------------------------
    def startThread(self, function, *args):
        """"""
        if args:
            args = tuple(args)
        threading.Thread(target = function, args = args).start()

    #----------------------------------------------------------------------
    def checkFolders(self, path):
        """"""
        command = f"if [ -d {path} ]; then echo exists; fi;"
        exists = self.sshCommand(command)
        return exists

    #----------------------------------------------------------------------
    def submitJob(self, project, cpus, memory, duration):
        """"""
        logText = self.getLogFunction()
        projectPath = self.configDict['projectPath']
        imgName = self.configDict['imgName']
        cookiesPath = f'{projectPath}{project}/cookies'
        homePath = f'{projectPath}{project}'
        imagePath = f'{projectPath}{imgName}'

        if not (self.checkFolders(cookiesPath)):
            logText(f'folder {homePath} or {cookiesPath} does not exist, '
                    f'make sure to create them!')
            return False

        if not duration:
            duration = '1'
        duration = f'{duration}::'
        if not memory:
            memory = 8
        vmem = f"{memory}G"
        port = str(random.randint(8787, 10000))
        if not cpus:
            cpus = 1
        cps = f'-pe threaded {cpus} '
        qsub = 'qsub -b yes -cwd -V -q all.q -N singInstance '
        qrunCommand = f"{qsub} -l h_rt={duration} -l h_vmem={vmem} {cps}"
        rserverOptions = f"--www-port={port} --auth-minimum-user-id=100 --server-set-umask=0"
        exCommand = (f'{qrunCommand} "singularity exec '
                     f'-B {cookiesPath}:/tmp '
                     f'-H {homePath} '
                     f'{imagePath} '
                     f'rserver {rserverOptions} "')



        logText('submitting: ' + exCommand + "\n")# self.startThread(logText, 'submitting: ' + sshCommand)  #
        jobOutput = self.sshCommand(exCommand)
        logText(jobOutput)

        jobNumberPattern = re.compile("Your job (\d+) ")
        jobNumber = jobNumberPattern.search(jobOutput).group(1)

        logText(f'Job number is {jobNumber}, waiting for job to run...\n')

        nodeID = ''
        while True:
            if nodeID != '':
                logText(f'job running on node {nodeID}!\n')
                break
            else:
                time.sleep(10)
                logText(f'job is still in queue...\n')

            qstatTable = self.qstat()

            if jobNumber not in qstatTable:
                logText('the submitted job is no longer in the queue, '
                        'maybe it executed and shut down due to an error?')
                return False
            elif qstatTable[jobNumber][0] == 'r':
                nodeID = qstatTable[jobNumber][1]

        self.updateRunningJobs(project, port, duration[0], nodeID, jobNumber)
        userHomePath = os.path.expanduser("~/")
        pickle.dump(dict(self.runningJobs), open(userHomePath + '.jobs.pkl', 'wb') )

        self.startThread(self.connectToJob(jobNumber))

    #----------------------------------------------------------------------
    def qstat(self):
        """"""
        qstatOutput = self.sshCommand('qstat')
        qstatList = qstatOutput.split("\n")[2:]

        nodePattern = re.compile("all.q@(n\d+).")
        qstatTable = {}
        for job in qstatList:
            if job == '' :
                continue
            fields = job.split()
            number = fields[0]
            state = fields[4]
            node = fields[7]

            if state == 'r':
                nodeID = nodePattern.search(node).group(1)
            else:
                nodeID = ''

            qstatTable[number] = [state, nodeID]

        return qstatTable

    #----------------------------------------------------------------------
    def updateRunningJobs(self, name, port, time, nodeID, jobNumber):
        """"""
        stopTime = datetime.now() + timedelta(hours= int(time))
        self.runningJobs.update({jobNumber: [port, stopTime, nodeID, name],})

    #----------------------------------------------------------------------
    def getSelectedJob(self):
        """"""
        if self.selectedJob:
            return self.selectedJob
        else:
            logText = self.getLogFunction()
            logText("No project selected, select one first!")
            return 0

    #----------------------------------------------------------------------
    def sshCommand(self, command, host = ''):
        """"""
        if not host:
            host = self.configDict['host']
        sshCommand = f"ssh {host} '{command}'"
        try:
            jobOutput = subprocess.check_output(sshCommand, shell = True)
        except subprocess.CalledProcessError as e:
            try:
                logText = self.getLogFunction()
                logText(f'Exit code {e.returncode} when executing {e.cmd}')
            except AttributeError:
                return False
            return False
        return jobOutput.decode("utf-8")

    #----------------------------------------------------------------------
    def deleteJob(self, ):
        """"""
        selectedJobN = self.getSelectedJob()
        if selectedJobN:
            logText = self.getLogFunction()
            qstatTable = self.qstat
            if selectedJobN in qstatTable and qstatTable[selectedJobN][0] == 'r':
                command = f'qdel {selectedJobN}'
                commandOutput = self.sshCommand(command)
                logText(commandOutput)
            else:
                logText(f'Job number {selectedJobN} is already shut down.')

            self.currentConnection[selectedJobN][0].kill()
            del self.runningJobs[selectedJobN]
            del self.currentConnection[selectedJobN]

    #----------------------------------------------------------------------
    def reconnectAll(self, *args):
        """"""
        logText = self.getLogFunction()
        logText('Reconnecting to all jobs...')
        i = 0

        for jobNumber in self.runningJobs:
            i += 1
            if jobNumber in self.currentConnection:
                self.currentConnection[jobNumber][0].kill()
            self.connectToJob(jobNumber)
        time.sleep(3)
        if i:
            logText('...Reconnected.')
        else:
            logText('...Nothing to reconnect to.')

    #----------------------------------------------------------------------
    def connectToJob(self, jobNumber):
        """"""
        host = self.configDict['host']
        port = self.runningJobs[jobNumber][0]
        nodeID = self.runningJobs[jobNumber][2]
        projectName = self.runningJobs[jobNumber][3]
        tunnelCommand = f'ssh -L {port}:{nodeID}:{port} {host}'
        try:
            tunnel = subprocess.Popen(tunnelCommand, shell = True)
        except subprocess.CalledProcessError as e:
            textLog = self.getLogFunction()
            textLog(f'Could not create tunnel using the command "{tunnelCommand}"')
            return False
        if jobNumber in self.currentConnection:
            del self.currentConnection[jobNumber]
        self.currentConnection[jobNumber] = [tunnel, port, projectName]

    #----------------------------------------------------------------------
    def on_currentConnection(self, instance, value):
        """"""
        if value:
            logText = self.getLogFunction()
            time.sleep(3)
            tempText = ''
            for jobNumber in value:
                connection = value[jobNumber]
                tempText += f'YOU ARE CONNECTED TO {connection[2]} ON PORT {connection[1]}\n'
            self.parent.parent.ids.connectionText.text = tempText
            self.parent.parent.ids.connectionText.background_color = 0.5, 0, 0, 1
        else:
            self.parent.parent.ids.connectionText.text = "YOU ARE NOT CONNECTED"
            self.parent.parent.ids.connectionText.background_color = 1, 1, 1, 1

    #----------------------------------------------------------------------
    def getLogFunction(self):
        """"""
        return self.parent.parent.ids.logOutputLabel.logText



#ROOT WIDGET
class RootWidget(BoxLayout):
    """"""
    logOutputLabel = ObjectProperty(None)
    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
        """Constructor"""
        #initialize base window and set orientation
        super(RootWidget, self).__init__(**kwargs)




#########################################################################
class GuiApp(App):
    """"""

    #----------------------------------------------------------------------
    def build(self):
        """Constructor"""
        self.icon = 'RRS_logo.png'
        self.title = 'Rstudio Reproducibility Suite V0.1'
        return RootWidget()



if __name__ == '__main__':


    GuiApp().run()


