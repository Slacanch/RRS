import re
import time
import subprocess

# 1
project = 'testProject'
duration = '3::'
vmem = "3G"
qrunCommand = f"qrun.sh -N singInstance -l h_rt={duration} -l h_vmem={vmem}"

exCommand = (f'{qrunCommand} "singularity exec '
             f'-H /hpc/pmc_gen/tcandelli/ContainerTest/{project} '
             f'/hpc/pmc_gen/tcandelli/ContainerTest/rstudio.simg2 '
             f'rserver"')

sshCommand = f"ssh hpc '{exCommand}'"

print(sshCommand)



jobOutput = subprocess.check_output(sshCommand, shell = True)
print(jobOutput)

jobNumberPattern = re.compile("Your job (\d+) ")
jobNumber = jobNumberPattern.search(jobOutput.decode("utf-8") ).group(1)

# 2
nodePattern = re.compile("all.q@(n\d+).")
nodeID = ''
while True:
    if nodeID != '':
        break
    else:
        time.sleep(10)

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



print(nodeID)
#3

tunnelCommand = f'ssh -L 8787:{nodeID}:8787 hpc'

tunnel = subprocess.Popen(tunnelCommand, shell = True)

tunnel.wait()
