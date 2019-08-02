import paramiko
from sshtunnel import SSHTunnelForwarder

class SshDirect:
    """"""

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""

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
                cps = ''
            else:
                cps = f'-pe threaded {cpus} '

            qsub = 'qsub -b yes -cwd -V -q all.q -N singInstance '
            qrunCommand = f"{qsub} -l h_rt={duration} -l h_vmem={vmem} {cps}"
            rserverOptions = f"--www-port={port} --auth-minimum-user-id=100 --server-set-umask=0"
            exCommand = (f'{qrunCommand} "singularity exec '
                         f'-B {cookiesPath}:/tmp '
                         f'-H {homePath} '
                         f'{imagePath} '
                         f'rserver {rserverOptions} "')



            logText('submitting: ' + exCommand + "\n")
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



