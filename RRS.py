#!/usr/bin/env python
import os
import re
import time
import json
import random
import pickle
import threading
import webbrowser
from datetime import datetime, timedelta
from functools import partial
import paramiko
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.lang.builder import Builder
from kivy.uix.boxlayout import BoxLayout
from sshtunnel import SSHTunnelForwarder
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import DictProperty, StringProperty, ObjectProperty

Builder.load_string("""
#:import FadeTransition kivy.uix.screenmanager.FadeTransition

<SplScreenManager>
    id: sm
    transition: FadeTransition()
    SplashScreen:
        id: ss
        name: 'splashscreen'
        manager: 'sm'
        BoxLayout:
            orientation: 'vertical'
            Image:
                source: 'RRS_logo.png'
            Label:
                id: splashLabel
                text: 'starting up...'
                size_hint: 1, 0.1
    MainScreen:
        id: ms
        name: 'mscreen'
        manager: 'sm'
        RootWidget:
            id: rootwid

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
    size_hint: [0.6,0.6]
    auto_dismiss: False
    projectPath: projectPathText
    host: hostText
    imgName: imgNameText
    pos_hint: {'center_x':0.5, 'center_y':0.5}
    BoxLayout:
        orientation: 'vertical'
        Button:
            size_hint: 1, 0.25
            id: help
            text: 'Open RRS help page'
            on_press: root.openHelp()
        Button:
            size_hint: 1, 0.25
            id: hpcReconnect
            text: 'Re-establish ssh connection with the hpc'
            on_press: root.hpcReconnect()
        GridLayout:
            cols: 2
            Button:
                id: help
                text: 'Slurm'
                on_press: root.setSlurmQueue()
            Button:
                id: help
                text: 'SGE'
                on_press: root.setSGEQueue()
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
            text: "No tunnels"
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
        defaultQueueSystem = 'slurm'
        defaultSSHHost = 'hpc'
        defaultProjectPath = '/hpc/pmc_gen/rstudio/'
        defaultImg = 'rstudio.simg'
        confDict = {'queue' : defaultQueueSystem,
                    'host': defaultSSHHost,
                    'projectPath': defaultProjectPath,
                    'imgName': defaultImg,}

        return confDict

class ConfigPopup(Popup):
    """"""

    queue = ObjectProperty(None)
    projectPath = ObjectProperty(None)
    host = ObjectProperty(None)
    imgName = ObjectProperty(None)

    currConfig = readConfig()
    if 'currQueue' not in currConfig:
        currConfig['queue'] = 'slurm'
    currQueue = StringProperty(currConfig['queue'])
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
        newConfigDict = {'queue': self.currConfig['queue'],
                         'host': self.host.text,
                         'projectPath': self.projectPath.text,
                         'imgName': self.imgName.text,}
        if newConfigDict['host']:
            tempHost = self.joblist.ssh
            self.joblist.ssh = self.joblist.sshObjectInit(newConfigDict['host'])
            if not self.joblist.ssh or not self.joblist.checkHPCConnection():
                textLog = self.joblist.getLogFunction()
                newHost = newConfigDict['host']
                textLog(f'the SSH host you tried to set ({newHost}) does not appear to connect correctly '
                    f'Is the host name spelled correctly? does the host allow passwordless connection? '
                    f'(test with ssh <hostname> to check if passwordless login is possible). '
                    f'reverting to the previosus ssh host now.')
                self.joblist.ssh = tempHost
                self.host.text = ''
                self.dismiss()
                return True


        for i in currConfigDict:
            if newConfigDict[i]:
                currConfigDict[i] = newConfigDict[i]


        self.joblist.configDict = currConfigDict
        self.joblist.saveConfig()
        if not self.joblist.startupped:
            self.joblist.startThread(self.joblist.startup)
        self.dismiss()

    #----------------------------------------------------------------------
    def setSlurmQueue(self):
        """"""
        self.currQueue = 'slurm'
    
    #----------------------------------------------------------------------
    def setSGEQueue(self):
        """"""
        self.currQueue = 'sge'  

    #----------------------------------------------------------------------
    def openHelp(self):
        """"""
        url = f'https://wiki.bioinf.prinsesmaximacentrum.nl/Singlecellgenomics/WebHome'
        webbrowser.open_new_tab(url)

    #----------------------------------------------------------------------
    def hpcReconnect(self):
        """"""
        self.joblist.ssh = self.joblist.sshCheckAlive(force = True)

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
        self.startupped = 0
        self.sshAlive = False
        self.resPop = ResourcePopup(self)
        self.confOpen = ConfigPopup(self, self.configDict)
        
        # check which queue checking to use
        if self.configDict['queue'] == 'sge':
            self.checkQueue = self.qstat
        if self.configDict['queue'] == 'slurm':
            self.checkQueue = self.slurmStat
        else:
            raise('lolwat?')
        
        self.startThread(self.startup)

    #----------------------------------------------------------------------
    def sshCheckAlive(self, *args, force = False, ):
        """"""


        if self.sshAlive or force:
            try:
                alive = self.ssh.get_transport().isAlive()
            except:
                alive = False

            if not alive:
                logText = self.getLogFunction()
                logText("the SSH connection seems to have failed. "
                        "Attempting to reconnect to the hpc now...")
                self.sshAlive = False
                self.ssh = self.sshObjectInit()
                if self.ssh:
                    try:
                        alive = self.ssh.get_transport().isAlive()
                    except:
                        alive = False
                    if not alive:
                        logText("Unable to reconnect, is your internet connection "
                                "working? you can re-establish connection with the "
                                "hpc in the settings.")
                        self.sshAlive = False
                    else:
                        self.sshAlive = True
                        logText('Connection reestablished.')
                else:
                    logText("Unable to reconnect, is your internet connection "
                            "working? you can re-establish connection with the "
                            "hpc in the settings.")
                    self.sshAlive = False


    #----------------------------------------------------------------------
    def sshObjectInit(self, host = None):
        """"""
        logText = self.getLogFunction()
        if not host:
            host = self.configDict['host']


        ssh_config = paramiko.SSHConfig()
        user_config_file = os.path.expanduser("~/.ssh/config")

        try:
            with open(user_config_file) as f:
                ssh_config.parse(f)
        except:
            logText("Could not parse ~/.ssh/config, does the file exist?")
            return None

        try:
            hpcConfig = ssh_config.lookup(host)
            proxy = paramiko.ProxyCommand(hpcConfig['proxycommand'])
            assert hpcConfig['hostname']
            assert hpcConfig['user']
        except:
            logText("host configuration seems to be incorrect. the host must be "
                    "configured to have a hostname, username and proxy command.")
            return None

        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.load_system_host_keys()

            client.connect(hpcConfig['hostname'], username= hpcConfig['user'], sock=proxy)
            client.get_transport().set_keepalive(15)
            self.sshAlive = True

            return client
        except:
            logText("failed to connect to the hpc, internet not working?")
            return None

    #----------------------------------------------------------------------
    def startup(self, ):
        """"""
        time.sleep(0.5)
        self.logText = self.getLogFunction()

        self.ssh = self.sshObjectInit()

        userHomePath = os.path.expanduser("~/")
        if os.path.isfile(userHomePath + '.jobs.pkl'):
            loadedRunningJobs = pickle.load(open(userHomePath + '.jobs.pkl', 'rb'))
        else:
            loadedRunningJobs = {}

        self.logText('startup commencing.')
        if self.ssh and self.checkHPCConnection():
            self.logText('checking connection and loading running jobs if present...')
            self.runningJobs =  self.checkJobs(loadedRunningJobs)
            if self.runningJobs:
                self.logText('Done!')
            else:
                self.logText('No jobs found.')
            self.sshAlive = True
            self.startupped = True
            Clock.schedule_interval(self.sshCheckAlive, 20)
            self.logText('startup completed.')
        else:
            self.logText('startup failed.')
            self.runningJobs = {}
            if self.ssh:
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
        if not self.startupped:
            textLog(f'startup will be performed when hpc connection is properly configured.')
    #----------------------------------------------------------------------
    def checkHPCConnection(self):
        """"""
        check = self.sshCommand('echo gooby')
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
                    self.currentConnection[i][0].close()
                del self.runningJobs[i]
                del self.currentConnection[i]
        return True

    #----------------------------------------------------------------------
    def checkJobs(self, loadedRunningJobs):
        """"""

        qstatTable = self.checkQueue()
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
    def on_runningJobs(self, *args):
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
        if self.sshAlive:
            logText = self.getLogFunction()
            queue = self.configDict['queue']
            projectPath = self.configDict['projectPath']
            imgName = self.configDict['imgName']
            cookiesPath = f'{projectPath}{project}/cookies'
            homePath = f'{projectPath}{project}'
            imagePath = f'{projectPath}{imgName}'

            if not (self.checkFolders(cookiesPath)):
                logText(f'folder {homePath} or {cookiesPath} does not exist, '
                        f'make sure to create them!')
                return False
            
            # CONSTRUCTING COMMANDS
            # SGE
            if queue == 'sge':
                if not duration:
                    duration = '1'
                duration = f'{duration}::'
                if not memory:
                    memory = 8
                vmem = f"{memory}G"
                port = str(random.randint(8787, 10000))
                if not cpus or int(cpus) == 1:
                    cps = ''  # do not use -pe threaded 1, it makes a mess due to sge bug
                else:
                    cps = f'-pe threaded {cpus} '  # use -pe threaded n if there's more than 1 cpu
    
                qsub = 'qsub -b yes -cwd -V -q all.q -N singInstance '
                qrunCommand = f"{qsub} -l h_rt={duration} -l h_vmem={vmem} {cps}"
                rserverOptions = f"--www-port={port} --auth-minimum-user-id=100 --server-set-umask=0"
                exCommand = (f'{qrunCommand} "singularity exec '
                             f'-B {cookiesPath}:/tmp '
                             f'-H {homePath} '
                             f'{imagePath} '
                             f'rserver {rserverOptions} "')
            elif queue == 'slurm':
                if not duration:
                    duration = '1'
                duration = f'{duration}:0:0'
                if not memory:
                    memory = 8
                vmem = f"{memory}G"
                port = str(random.randint(8787, 10000))
                if not cpus:
                    cps = '-c 1'  
                else:
                    cps = f'-c {cpus} '  
    
                qsub = 'sbatch  --export=ALL --job-name=singInstance '
                qrunCommand = f"{qsub} --time={duration} --mem={vmem} {cps}"
                rserverOptions = f"--www-port={port} --auth-minimum-user-id=100 --server-set-umask=0"
                exCommand = (f'{qrunCommand} --wrap="singularity exec '
                                           f'-B {cookiesPath}:/tmp '
                                           f'-H {homePath} '
                                           f'{imagePath} '
                                           f'rserver {rserverOptions} "')                


            logText('submitting: ' + exCommand + "\n")# self.startThread(logText, 'submitting: ' + sshCommand)  #
            jobOutput = self.sshCommand(exCommand)
            logText(jobOutput)

            jobNumberPattern = re.compile(".+? job (\d+)")
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

                qstatTable = self.checkQueue()

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
        else:
            self.logText("no hpc connection, cannot start new job.")

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
    def slurmStat(self):
        """"""
        #user = self.sshCommand('echo $USER')
        qstatOutput = self.sshCommand('squeue -u $USER')
        qstatList = qstatOutput.split("\n")[1:]

        sbatchTable = {}
        for job in qstatList:
            if job == '' :
                continue
            fields = job.split()
            number = fields[0]
            state = fields[4].lower() # turning to lower allows same logic to work for both sge and slurm
            node = fields[7]

            if state == 'r':
                nodeID = node
            else:
                nodeID = ''

            sbatchTable[number] = [state, nodeID]

        return sbatchTable        

    #----------------------------------------------------------------------
    def updateRunningJobs(self, name, port, timeReq, nodeID, jobNumber):
        """"""
        stopTime = datetime.now() + timedelta(hours= int(timeReq))
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
    def sshCommand(self, command, ssh = None):
        """"""
        if not ssh:
            ssh = self.ssh
        try:
            (stdin, stdout, stderr) = ssh.exec_command(command)
        except :
            print('SSH PROBLEMS')
            return False
        print("".join(stderr.readlines()))
        return "".join(stdout.readlines())

    #----------------------------------------------------------------------
    def deleteJob(self, ):
        """"""
        if self.sshAlive:
            selectedJobN = self.getSelectedJob()
            if selectedJobN:
                logText = self.getLogFunction()
                qstatTable = self.checkQueue()
                if selectedJobN in qstatTable and qstatTable[selectedJobN][0] == 'r':
                    if self.configDict['queue'] == 'sge':
                        command = f'qdel {selectedJobN}'
                    elif self.configDict['queue'] == 'slurm':
                        command = f'scancel {selectedJobN}'
                    commandOutput = self.sshCommand(command)
                    logText(commandOutput)
                else:
                    logText(f'Job number {selectedJobN} is already shut down.')

                self.currentConnection[selectedJobN][0].close()
                del self.runningJobs[selectedJobN]
                del self.currentConnection[selectedJobN]
        else:
            self.logText('no hpc connection, cannot delete job')
    #----------------------------------------------------------------------
    def reconnectAll(self, *args):
        """"""
        if self.sshAlive:
            logText = self.getLogFunction()
            logText('Reconnecting to all jobs...')
            i = 0

            for jobNumber in self.runningJobs:
                i += 1
                if jobNumber in self.currentConnection:
                    self.currentConnection[jobNumber][0].close()
                self.connectToJob(jobNumber)
            if i:
                logText('...Reconnected.')
            else:
                logText('...Nothing to reconnect to.')
        else:
            self.logText("no hpc connection, cannot reconnect.")
    #----------------------------------------------------------------------
    def connectToJob(self, jobNumber):
        """"""
        host = self.configDict['host']
        port = self.runningJobs[jobNumber][0]
        nodeID = self.runningJobs[jobNumber][2]
        projectName = self.runningJobs[jobNumber][3]
        user_config_file = os.path.expanduser("~/.ssh/config")
        try:
            tunnel = SSHTunnelForwarder(host,ssh_config_file = user_config_file,
                                        remote_bind_address = (nodeID, int(port)),
                                        local_bind_address = ('localhost', int(port)),
                                        allow_agent = True, ssh_password = '',
                                        set_keepalive= 10)
            tunnel.start()
        except:
            textLog = self.getLogFunction()
            textLog(f'Could not create tunnel')
            return False
        if jobNumber in self.currentConnection:
            self.currentConnection[jobNumber][0].close()
            del self.currentConnection[jobNumber]
        self.currentConnection[jobNumber] = [tunnel, port, projectName]

    #----------------------------------------------------------------------
    def on_currentConnection(self, instance, value):
        """"""
        if value:
            tempText = ''
            for jobNumber in value:
                connection = value[jobNumber]
                tempText += f'SSH tunnel  established to project  {connection[2]} on port {connection[1]}\n'
            self.parent.parent.ids.connectionText.text = tempText
            self.parent.parent.ids.connectionText.background_color = 0.5, 0, 0, 1
        else:
            self.parent.parent.ids.connectionText.text = "no SSH tunnel established"
            self.parent.parent.ids.connectionText.background_color = 1, 1, 1, 1

    #----------------------------------------------------------------------
    def getLogFunction(self):
        """"""
        return self.parent.parent.ids.logOutputLabel.logText



#ROOT WIDGET
class RootWidget(BoxLayout):
    """"""
    logOutputLabel = ObjectProperty(None)


class SplashScreen(Screen):
    def skip(self, *args):
        self.parent.current = "mscreen"


class MainScreen(Screen):
    #----------------------------------------------------------------------
    def initializeWidget(self, *args):
        """"""
        self.add_widget(RootWidget())

class SplScreenManager(ScreenManager):
    """"""

    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
        """Constructor"""
        super(SplScreenManager, self).__init__(**kwargs)
        self.current = 'splashscreen'
        Clock.schedule_once(self.screens[0].skip, 10)


#########################################################################
class GuiApp(App):
    """"""

    #----------------------------------------------------------------------
    def build(self):
        """Constructor"""
        self.icon = 'RRS_logo.png'
        self.title = 'Rstudio Reproducibility Suite V0.1.1 (pe threaded fix)'

        return SplScreenManager()

    #----------------------------------------------------------------------
    def on_stop(self):
        """"""
        currentApp = App.get_running_app()
        connections = currentApp.root.ids['rootwid'].ids['joblist'].currentConnection

        for connection in connections:
            connections[connection][0].close()

if __name__ == '__main__':
    GuiApp().run()