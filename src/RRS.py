#!/usr/bin/env python
import os
import re
import time
import json
import random
import pickle
import threading
import webbrowser
from types import SimpleNamespace
from datetime import datetime, timedelta
from functools import partial
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.lang.builder import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import DictProperty, StringProperty, ObjectProperty

#----------------------------------------------------------------------
def startThread(self, function, *args):
    """"""
    if args:
        args = tuple(args)
    threading.Thread(target = function, args = args).start()

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







#----------------------------------------------------------------------
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
    def saveConfig(self):
        """"""
        logText = self.getLogFunction()
        logText('saving configuration...')
        configFile = os.path.expanduser("~/.RRS_config")
        json.dump(self.configDict, open(configFile, 'w'))
        logText("saved!")

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
    def logText(self, value):
        """"""
        currentTime = str(datetime.now().time()).split('.')[0]
        if not value.endswith("\n"):
            value = value + '\n'
        self.text = currentTime + ": " + value + self.text


class RootWidget(BoxLayout):
    """"""
    logOutputLabel = ObjectProperty(None)

    runningJobs = DictProperty({}) # {jobnumber: [port, stopTime, nodeID, name]}
    currentButtons = {}
    currentConnection = DictProperty({})
    configDict = readConfig()

    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
        """Constructor"""
        super(RootWidget, self).__init__(**kwargs)
        self.selectedJob = ''
        self.startupped = 0
        self.resPop = ResourcePopup(self)
        self.confOpen = ConfigPopup(self, self.configDict)

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
    def startup(self, ):
        """"""
        time.sleep(0.5)
        self.logText = self.getLogFunction()

        self.ssh = SshDirect(self.configDict, self.logText)

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
                                              " will stop in: " + deltaReadable)
            if deltaReadable == '0:00:01':
                textLog = self.getLogFunction()
                textLog(f'{project} job with number {i} has expired and will be closed.')
                if self.currentConnection[i]:
                    self.currentConnection[i][0].close()
                del self.runningJobs[i]
                del self.currentConnection[i]
        return True



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
    def getSelectedJob(self):
        """"""
        if self.selectedJob:
            return self.selectedJob
        else:
            logText = self.getLogFunction()
            logText("No project selected, select one first!")
            return 0




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
    def on_currentConnection(self, instance, value):
        """"""
        if value:
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
        return self.ids.logOutputLabel.logText

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
    def on_runningJobs(self, *args):
        """"""
        self.removeButtons()
        self.drawButtons()

#----------------------------------------------------------------------
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
class RRSApp(App):
    """"""

    #----------------------------------------------------------------------
    def build(self):
        """Constructor"""
        self.icon = 'RRS_logo.png'
        self.title = 'Rstudio Reproducibility Suite V0.1'
        return SplScreenManager()

    #----------------------------------------------------------------------
    def on_stop(self):
        """"""
        currentApp = App.get_running_app()
        connections = currentApp.root.ids['rootwid'].ids['joblist'].currentConnection

        for connection in connections:
            connections[connection][0].close()

if __name__ == '__main__':
    RRSApp().run()







