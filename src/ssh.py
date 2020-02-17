import re
import pickle
import paramiko
from sshtunnel import SSHTunnelForwarder



class SshDirect:
    """"""

    #----------------------------------------------------------------------
    def __init__(self, config, logText):
        """Constructor"""
        #setup
        self.logText = logText
        self.projectPath = config['projectPath']
        self.host = config['host']
        self.image = config['imgName']

        # read in ssh config
        ssh_config = paramiko.SSHConfig()
        user_config_file = os.path.expanduser("~/.ssh/config")

        try:
            with open(user_config_file) as f:
                ssh_config.parse(f)
        except (IOError, FileNotFoundError):
            self.logText("Could not parse ~/.ssh/config, does the file exist?")
            raise FileNotFoundError

        # getting host information
        try:
            hpcConfig = ssh_config.lookup(host)
            proxy = paramiko.ProxyCommand(hpcConfig['proxycommand'])
            assert hpcConfig['hostname']
            assert hpcConfig['user']
        except (AssertionError, paramiko.ssh_exception.SSHException) as e:
            self.logText("host configuration seems to be incorrect. the host must be "
                    "configured to have a hostname, username and proxy command.")
            raise

        # ssh client initialization
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.load_system_host_keys()

            client.connect(hpcConfig['hostname'], username= hpcConfig['user'], sock=proxy)
            client.get_transport().set_keepalive(15)

            self.client = client
        except:
            self.logText("failed to connect to the hpc, internet not working?")
            raise

    #----------------------------------------------------------------------
    def checkFolders(self, path):
        """"""
        command = f"if [ -d {path} ]; then echo exists; fi;"
        exists = self.sshCommand(command)
        return exists

    #----------------------------------------------------------------------
    def checkHPCConnection(self):
        """"""
        check = self.sshCommand('echo gooby')
        return check

    #----------------------------------------------------------------------
    def sshCommand(self, command):
        """"""
        try:
            (stdin, stdout, stderr) = self.ssh.exec_command(command)
        except paramiko.ssh_exception.SSHException as e:
            self.logText(f"Could not submit {command}. "
                         f"{e.with_traceback()}")
            return None
        print("".join(stderr.readlines()))
        return "".join(stdout.readlines())

    #----------------------------------------------------------------------
    def submitJob(self, project, cpus, memory, duration):
        """"""
        tmpPath = f'{self.projectPath}{project}/tmp'
        homePath = f'{self.projectPath}{project}'
        imagePath = f'{self.projectPath}{self.imgName}'

        if not (self.checkFolders(tmpPath)):
            self.logText(f'folder {homePath} or {tmpPath} does not exist, '
                    f'make sure to create them!')
            return False

        if not duration:
            duration = '1'
        duration = f'{duration}::'
        if not memory:
            memory = 8
        vmem = f"{memory}G"
        port = str(random.randint(8787, 60000))
        if not cpus:
            cps = ''
        else:
            cps = f'-pe threaded {cpus} '

        qsub = 'qsub -b yes -cwd -V -q all.q -N singInstance '
        qrunCommand = f"{qsub} -l h_rt={duration} -l h_vmem={vmem} {cps}"
        rserverOptions = f"--www-port={port} --auth-minimum-user-id=100 --server-set-umask=0"
        exCommand = (f'{qrunCommand} "singularity exec '
                     f'-B {tmpPath}:/tmp '
                     f'-H {homePath} '
                     f'{imagePath} '
                     f'rserver {rserverOptions} "')



        self.logText('submitting: ' + exCommand + "\n")
        jobOutput = self.sshCommand(exCommand)
        self.logText(jobOutput)

        jobNumberPattern = re.compile("Your job (\d+) ")
        jobNumber = jobNumberPattern.search(jobOutput).group(1)

        self.logText(f'Job number is {jobNumber}, waiting for job to run...\n')

        nodeID = ''
        while True:
            if nodeID != '':
                self.logText(f'job running on node {nodeID}!\n')
                break
            else:
                time.sleep(10)
                self.logText(f'job is still in queue...\n')

            qstatTable = self.qstat()

            if jobNumber not in qstatTable:
                self.logText('the submitted job is no longer in the queue, '
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
    def deleteJob(self, ):
        """"""
        if self.sshAlive:
            selectedJobN = self.getSelectedJob()
            if selectedJobN:
                logText = self.getLogFunction()
                qstatTable = self.qstat()
                if selectedJobN in qstatTable and qstatTable[selectedJobN][0] == 'r':
                    command = f'qdel {selectedJobN}'
                    commandOutput = self.sshCommand(command)
                    logText(commandOutput)
                else:
                    logText(f'Job number {selectedJobN} is already shut down.')

                self.currentConnection[selectedJobN][0].close()
                del self.runningJobs[selectedJobN]
                del self.currentConnection[selectedJobN]
        else:
            self.logText('no hpc connection, cannot delete job')

class SshTunnel:
    """"""

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""



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


