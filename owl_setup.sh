#!/bin/bash

# Function to check the exit status of the last executed command
check_status() {
  if [ $? -ne 0 ]; then
    echo "[ERROR] $1 failed."
    exit 1
  else
    echo "[INFO] $1 completed successfully."
  fi
}

# Free up space
echo "[INFO] Freeing up space by removing unnecessary packages..."
sudo apt-get purge -y wolfram-engine
sudo apt-get purge -y libreoffice*
sudo apt-get clean
check_status "Cleaning up"

sudo apt-get autoremove -y
check_status "Removing unnecessary packages"

# Update the system and firmware
echo "[INFO] Updating the system and firmware..."
sudo apt-get update && sudo apt-get upgrade -y
check_status "System update and upgrade"

# Install virtualenv and virtualenvwrapper
echo "[INFO] Installing virtualenv and virtualenvwrapper..."
sudo apt-get install -y python3-virtualenv
check_status "Installing python3-virtualenv"

pip3 install virtualenvwrapper
check_status "Installing python3-virtualenvwrapper"

# Set up the virtual environment
echo "export WORKON_HOME=$HOME/.virtualenvs" >> ~/.bashrc
echo "export VIRTUALENVWRAPPER_PYTHON=/usr/bin/python3" >> ~/.bashrc
echo "export VIRTUALENVWRAPPER_VIRTUALENV=$HOME/.local/bin/virtualenv" >> ~/.bashrc
echo "source $HOME/.local/bin/virtualenvwrapper.sh" >> ~/.bashrc
source "$HOME/.local/bin/virtualenvwrapper.sh"
source ~/.bashrc
check_status "Updating .bashrc for virtualenvwrapper (local installation)"

# Verify that virtualenvwrapper is available

if ! command -v mkvirtualenv &> /dev/null; then
    echo "[ERROR] virtualenvwrapper is not available. Please check the installation."
    exit 1
fi

sleep 1s

# Create the owl virtual environment
echo "[INFO] Creating the 'owl' virtual environment..."
mkvirtualenv --python=/usr/bin/python3 --system-site-packages owl
check_status "Creating virtual environment 'owl'"

sleep 1s

# Install OpenCV in the owl virtual environment
echo "[INFO] Installing OpenCV in the 'owl' virtual environment..."
source $HOME/.virtualenvs/owl/bin/activate
sleep 1s
sudo apt-get install libopencv-dev python3-opencv
check_status "Installing OpenCV"

sleep 1s

# Install the OWL Python dependencies
echo "[INFO] Installing the OWL Python dependencies..."
cd ~/owl
pip install -r requirements.txt
check_status "Installing dependencies from requirements.txt"

# Make the scripts executable
echo "[INFO] Making scripts executable..."
chmod a+x owl.py
check_status "Making owl.py executable"

chmod a+x owl_boot.sh
check_status "Making owl_boot.sh executable"

chmod a+x owl_boot_wrapper.sh
check_status "Making owl_boot_wrapper.sh executable"

# Move the boot scripts to /usr/local/bin
echo "[INFO] Moving boot scripts to /usr/local/bin..."
sudo mv owl_boot.sh /usr/local/bin/owl_boot.sh
check_status "Moving owl_boot.sh"

sudo mv owl_boot_wrapper.sh /usr/local/bin/owl_boot_wrapper.sh
check_status "Moving owl_boot_wrapper.sh"

# Add the boot script to cron for startup
echo "[INFO] Adding boot script to cron..."
(crontab -l 2>/dev/null; echo "@reboot /usr/local/bin/owl_boot_wrapper.sh > /home/$USER/launch.log 2>&1") | sudo crontab -
check_status "Adding boot script to cron"

echo "[INFO] Setting owl-background.png as the desktop background..."
sed -i "/^wallpaper=/c\wallpaper=/home/$USER/owl/images/owl-background.png" ~/.config/pcmanfm/LXDE/desktop-items-0.conf
check_status "Setting desktop background"

echo "[INFO] OWL setup complete."
read -p "Start OWL focusing? (y/n): " choice
case "$choice" in
  y|Y ) echo "[INFO] Starting focusing..."; ./owl.py --focus;;
  n|N ) echo "[INFO] Focusing skipped. Run './owl.py --focus' to focus the OWL at a later point";;
  * ) echo "[ERROR] Invalid input. Please enter y or n.";;
esac
read -p "Launch OWL software? (y/n): " choice
case "$choice" in
  y|Y ) echo "[INFO] Launching OWL..."; ./owl.py --show-display;;
  n|N ) echo "[INFO] Skipped. Run './owl.py --show-display' to launch the OWL at a later point";;
  * ) echo "[ERROR] Invalid input. Please enter y or n.";;
esac