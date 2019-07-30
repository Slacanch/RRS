# Rstudio Reproducibility Suite

RRS is a graphical interface macOS app that allows users to work with Rstudio in a reproducible manner in the context of a Sun Grid Engine (SGE) cluster environment. 

RRS makes use of singularity containers running rstudio server and allows users to interface with it using a web browser. additionally RRS allows to work on any number of projects (even simultaneously), each with their own set of R packages. This ensures that each project stays self contained and reproducible.

## Requirements
RSS is written in python using the [kivy framework](https://kivy.org/#home) and packaged with [pyinstaller](https://pypi.org/project/PyInstaller/) and therefore does not require the python interpreter nor any packages.
It does, however, require a properly configured ssh host , as well as a singularity image able to run Rstudio server, and ability to create folders on your hpc environment.

### Ssh configuration
In order to connect and send commands to the HPC environment, RRS needs to connect to the HPC via ssh. to do so, it needs a properly configured ssh hpcst that allows passwordless login to your cluster environment. The host should contain--at a minimum--a hostname, username, proxy command, and identity file.

here's an example of a properly configured host:
```
Host hpc
  HostName <HPC hostname>
  User <HPC user>
  ProxyCommand ssh -i ~/.ssh/id_rsa_hpc -l <HPC User> <HPC gateway> nc %h %p 2>/dev/null
  UseKeychain yes
  AddKeysToAgent yes
  IdentityFile ~/.ssh/id_rsa_hpc
```

### Singularity image 

RRS needs a singularity image configured to run Rstudio server. The image can be customized to contain additional software as required. A functional image is included with the latest release.

### Project Folders

In RRS, projects are folders. Each Project folder will contain all the data and packages necessary for analysis. To be used by RRS Project folders need to be owned by the user performing the analysis.

## Installation
The .app binary, as well as a working singularity image are available as a github release. Unpack the zip and double click to launch.

## Usage
Tutorial coming soon. 


## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License
[GPL3](https://choosealicense.com/licenses/gpl-3.0/)

