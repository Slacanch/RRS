import kivy
import os
import re
import random
import time
import subprocess
import pickle
import threading
from datetime import datetime, timedelta
from functools import partial
from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.properties import DictProperty,  ListProperty, StringProperty, ObjectProperty
from kivy.uix.scrollview import ScrollView
from kivy.lang.builder import Builder
# maybe these should be withing the function that draws them?
# kivy properties will automatically set attributes for the class they are bound to (?), maybe that's the way it's supposed to work.

Builder.load_string("""
#:import Factory kivy.factory.Factory

<ResourcePopup>
    text: 'Resource settings'
    size_hint: [0.4,0.4]
    auto_dismiss: False
    project: projectText
    cpus: cpuText
    memory: memText
    duration: timeText
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

<RootWidget>
    id: rootwid
    BoxLayout:
        id: box
        orientation: 'vertical'
        Label:
            id: connectionText
            size_hint: 1, 0.4
            text: "YOU ARE NOT CONNECTED"
        GridLayout:
            cols: 4
            size_hint: 1, 0.3
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
        Label:
            size_hint: 1, 0.1
            text: 'Running Jobs'
        JobList:
            id: joblist
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





class LogOutput(Label):
    """"""

    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
        """Constructor"""
        super(LogOutput, self).__init__(**kwargs)

    #----------------------------------------------------------------------
    def logText(self, value):
        """"""
        if not value.endswith("\n"):
            value = value + '\n'
        self.text = value + self.text



class TestScroll(ScrollView):
    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
        """Constructor"""
        super(TestScroll, self).__init__(**kwargs)



class JobList(GridLayout):
    """"""
    runningJobs = DictProperty({}) # {'project1': ['port', 'timeLeft'], 'project2': ['port', 'timeLeft'],}
    currentButtons = {}
    connectionButtonIndex = 4
    currentConnection = DictProperty({})


    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
        """Constructor"""
        super(JobList, self).__init__(**kwargs)
        self.selectedJob = ''
        self.resPop = ResourcePopup(self)
        if os.path.isfile('jobs.pkl'):
            loadedRunningJobs = pickle.load(open('jobs.pkl', 'rb'))
            self.runningJobs = self.checkJobs(loadedRunningJobs)

    #----------------------------------------------------------------------
    def checkJobs(self, loadedRunningJobs):
        """"""
        qstatTable = self.qstat()

        keys = loadedRunningJobs.keys()
        for i in list(keys):
            if i not in qstatTable:
                del loadedRunningJobs[i]
        return loadedRunningJobs

    #----------------------------------------------------------------------
    def drawButtons(self):
        """"""

        for i in self.runningJobs:
            job = self.runningJobs[i]
            but = Button()  # size_hint_max_y = 0.5
            but.text = str("project: " + str(i) +
                           "  on port: " + str(job[0]) +
                           "  will stop at: " + str(job[1]))
            if i not in self.currentButtons:
                self.currentButtons[i] = but

            but.bind(on_press = partial(self.selectStuff, i))  #shohuld be moved to kv file
            self.add_widget(but)

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
        cookiesPath = f'/hpc/pmc_gen/rstudio/{project}/cookies'
        homePath = f'/hpc/pmc_gen/rstudio/{project}'

        if not (self.checkFolders(homePath) and self.checkFolders(cookiesPath)):
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
        cps = f'-p threaded={cpus} '

        qrunCommand = f"qrun.sh -N singInstance -l h_rt={duration} -l h_vmem={vmem} {cps}"

        exCommand = (f'{qrunCommand} "singularity exec '
                     f'-B {cookiesPath}:/tmp '  # /hpc/pmc_gen/tcandelli/ContainerTest/scratch{user}
                     f'-H {homePath} '
                     f'-B /hpc/pmc_gen/tcandelli/ContainerTest/scratchTito:/var/log '
                     f'/hpc/pmc_gen/tcandelli/ContainerTest/rstudio.simg2 '
                     f'rserver --www-port={port} --auth-minimum-user-id=100 "')

        # exCommand = (f'{qrunCommand} "singularity instance.start '
        #             f'-H /hpc/pmc_gen/rstudio/{project} '
        #             f'/hpc/pmc_gen/tcandelli/ContainerTest/rstudio.simg2 '
        #             f'{project}; sleep 5; singularity exec '
        #             f'instance://{project} rserver --www-port={port}"')


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
        pickle.dump(dict(self.runningJobs), open('jobs.pkl', 'wb') )

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
    def sshCommand(self, command):
        """"""
        sshCommand = f"ssh hpc '{command}'"
        try:
            jobOutput = subprocess.check_output(sshCommand, shell = True)
        except subprocess.CalledProcessError as e:
            logText = self.getLogFunction()
            logText(f'Exit code {e.returncode} when executing {e.cmd}')
            return False
        return jobOutput.decode("utf-8")

    #----------------------------------------------------------------------
    def deleteJob(self):
        """"""
        selectedJobN = self.getSelectedJob()
        if selectedJobN:
            logText = self.getLogFunction()
            command = f'qdel {selectedJobN}'
            commandOutput = self.sshCommand(command)
            logText(commandOutput)

            self.currentConnection[selectedJobN][0].kill()
            del self.runningJobs[selectedJobN]
            del self.currentConnection[selectedJobN]

    #----------------------------------------------------------------------
    def reconnectAll(self):
        """"""
        logText = self.getLogFunction()
        logText('Reconnecting to all jobs...')
        for jobNumber in self.runningJobs:
            if jobNumber in self.currentConnection:
                self.currentConnection[jobNumber][0].kill()
            self.connectToJob(jobNumber)
        time.sleep(3)
        logText('...Reconnected.')

    #----------------------------------------------------------------------
    def connectToJob(self, jobNumber):
        """"""
        port = self.runningJobs[jobNumber][0]
        nodeID = self.runningJobs[jobNumber][2]
        projectName = self.runningJobs[jobNumber][3]
        tunnelCommand = f'ssh -L {port}:{nodeID}:{port} hpc'
        tunnel = subprocess.Popen(tunnelCommand, shell = True)
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

    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
        """Constructor"""
        #initialize base window and set orientation
        super(RootWidget, self).__init__(**kwargs)

    #----------------------------------------------------------------------
    def changeProjects(self, widget):
        """"""
        # widget.removeButtons()
        widget.runningJobs['newproj'] = ['lalap', 'dereita']
        # widget.drawButtons()


#########################################################################
class GuiApp(App):
    """"""

    #----------------------------------------------------------------------
    def build(self):
        """Constructor"""
        self.title = 'Single Cell Project Manager V0.01'
        return RootWidget()




if __name__ == '__main__':
    GuiApp().run()


