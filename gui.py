import kivy
import os
import re
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
from kivy.properties import DictProperty,  ListProperty, StringProperty
from kivy.uix.scrollview import ScrollView
# maybe these should be withing the function that draws them?
# kivy properties will automatically set attributes for the class they are bound to (?), maybe that's the way it's supposed to work.


class ResourcePopup(Popup):
    """"""

    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
        """Constructor"""
        super(ResourcePopup, self).__init__(**kwargs)







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
    currentConnection = ListProperty([])


    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
        """Constructor"""
        super(JobList, self).__init__(**kwargs)
        self.selectedJob = ''
        if os.path.isfile('jobs.pkl'):
            loadedRunningJobs = pickle.load(open('jobs.pkl', 'rb'))
            self.runningJobs = self.checkJobs(loadedRunningJobs)



    #----------------------------------------------------------------------
    def checkJobs(self, loadedRunningJobs):
        """"""
        qstatOutput = subprocess.check_output("ssh hpc 'qstat'", shell = True)
        qstatList = qstatOutput.decode("utf-8") .split("\n")[2:]

        jobNumbers = []
        for job in qstatList:
            if job == '' :
                continue
            fields = job.split()
            number = fields[0]
            jobNumbers.append(number)

        keys = loadedRunningJobs.keys()
        for i in list(keys):
            if loadedRunningJobs[i][3] not in jobNumbers:
                del loadedRunningJobs[i]
        return loadedRunningJobs

    #----------------------------------------------------------------------
    def drawButtons(self):
        """"""

        for i in self.runningJobs:
            job = self.runningJobs[i]
            but = Button()  # size_hint_max_y = 0.5
            but.text = str("project: " + i + "  on port: " + job[0] + "  will stop at: " + str(job[1]))
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
    def submitJob(self):
        """"""
        resources = ResourcePopup()
        resources.open()
        project = 'testProject'
        duration = '0:10:'
        vmem = "3G"
        port = '8787'
        cps = '-p threaded=4 '
        logText = self.getLogFunction()
        qrunCommand = f"qrun.sh -N singInstance -l h_rt={duration} -l h_vmem={vmem}"

        exCommand = (f'{qrunCommand} "singularity exec '
                     f'-H /hpc/pmc_gen/tcandelli/ContainerTest/{project} '
                     f'/hpc/pmc_gen/tcandelli/ContainerTest/rstudio.simg2 '
                     f'rserver --www-port={port}"')

        sshCommand = f"ssh hpc '{exCommand}'"

        logText('submitting: ' + sshCommand + "\n")# self.startThread(logText, 'submitting: ' + sshCommand)  #

        jobOutput = subprocess.check_output(sshCommand, shell = True)
        logText(jobOutput.decode("utf-8"))

        #

        jobNumberPattern = re.compile("Your job (\d+) ")
        jobNumber = jobNumberPattern.search(jobOutput.decode("utf-8") ).group(1)

        logText(f'Job number is {jobNumber}, waiting for job to run...\n')

        nodePattern = re.compile("all.q@(n\d+).")
        nodeID = ''
        while True:
            if nodeID != '':
                logText(f'job running on node {nodeID}!\n')
                break
            else:
                time.sleep(10)
                logText(f'still waiting...\n')

            qstatOutput = subprocess.check_output("ssh hpc 'qstat'", shell = True)
            qstatList = qstatOutput.decode("utf-8") .split("\n")[2:]

            for job in qstatList:
                if job == '' :
                    continue
                fields = job.split()
                number = fields[0]
                state = fields[4]
                node = fields[7]

                if number == jobNumber:
                    if state == 'r':
                        nodeID = nodePattern.search(node).group(1)

        self.updateRunningJobs(project, port, duration[0], nodeID, jobNumber)
        pickle.dump(dict(self.runningJobs), open('jobs.pkl', 'wb') )

    #----------------------------------------------------------------------
    def updateRunningJobs(self, name, port, time, nodeID, jobNumber):
        """"""
        stopTime = datetime.now() + timedelta(hours= int(time))
        self.runningJobs.update({name: [port, stopTime, nodeID, jobNumber],})

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
        jobOutput = subprocess.check_output(sshCommand, shell = True)
        return jobOutput.decode("utf-8")

    #----------------------------------------------------------------------
    def deleteJob(self):
        """"""
        selectedName = self.getSelectedJob()
        if selectedName:
            logText = self.getLogFunction()
            jobNumber = self.runningJobs[selectedName][3]
            command = f'qdel {jobNumber}'
            commandOutput = self.sshCommand(command)
            logText(commandOutput)

            del self.runningJobs[selectedName]

            if selectedName == self.currentConnection[1]:
                self.currentConnection[0].kill()
                self.currentConnection = []

    #----------------------------------------------------------------------
    def connectToJob(self):
        """"""
        selectedName = self.getSelectedJob()
        if selectedName:
            logText = self.getLogFunction()
            port = self.runningJobs[selectedName][0]
            nodeID = self.runningJobs[selectedName][2]
            tunnelCommand = f'ssh -L {port}:{nodeID}:{port} hpc'
            logText('setting up tunnel...')
            tunnel = subprocess.Popen(tunnelCommand, shell = True)
            self.currentConnection = [tunnel, selectedName, port]

    #----------------------------------------------------------------------
    def on_currentConnection(self, instance, value):
        """"""
        if value:
            logText = self.getLogFunction()
            self.parent.parent.ids.connectionText.text = f'YOU ARE CONNECTED TO {value[1]} ON PORT {value[2]}'
            self.parent.parent.ids.connectionText.background_color = 1, 0, 0, 1
            logText("...Success! you may now connect.")
        else:
            self.parent.parent.ids.connectionText.text = "YOU ARE NOT CONNECTED"
            self.parent.parent.ids.connectionText.background_color = 1, 1, 1, 1

    #----------------------------------------------------------------------
    def getLogFunction(self):
        """"""
        return self.parent.parent.ids.logOutputLabel.logText

    #----------------------------------------------------------------------
    def disconnectFromJob(self):
        """"""
        if self.currentConnection:
            self.currentConnection[0].kill()
            self.currentConnection = []

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


