#!/bin/bash
# OpenWeedLocator Jetson Setup Script
# This script sets up OWL on NVIDIA Jetson devices (Orin Nano Super, Orin Nano, Xavier NX)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running on Jetson
check_jetson() {
    if [ -f /proc/device-tree/model ]; then
        MODEL=$(cat /proc/device-tree/model 2>/dev/null | tr -d '\0')
        if [[ $MODEL == *"Jetson"* ]]; then
            log_success "Detected Jetson device: $MODEL"
            return 0
        fi
    fi
    log_error "This script is designed for NVIDIA Jetson devices only!"
    exit 1
}

# Check JetPack version
check_jetpack() {
    if command -v jetson_release &> /dev/null; then
        JETPACK_VERSION=$(jetson_release -v 2>/dev/null | grep "JETPACK" | awk '{print $2}' || echo "Unknown")
        log_info "JetPack version: $JETPACK_VERSION"
    else
        log_warning "Cannot determine JetPack version. Ensure JetPack 5.0+ is installed."
    fi
}

# Install system dependencies
install_system_deps() {
    log_info "Installing system dependencies..."
    
    sudo apt update
    sudo apt install -y \
        python3-pip \
        python3-dev \
        python3-venv \
        git \
        cmake \
        build-essential \
        gstreamer1.0-tools \
        gstreamer1.0-plugins-good \
        gstreamer1.0-plugins-base \
        gstreamer1.0-plugins-bad \
        v4l-utils
    
    log_success "System dependencies installed"
}

# Install Jetson GPIO
install_jetson_gpio() {
    log_info "Installing Jetson.GPIO..."
    sudo pip3 install Jetson.GPIO
    log_success "Jetson.GPIO installed"
}

# Setup Python environment
setup_python_env() {
    log_info "Setting up Python virtual environment..."
    
    # Create virtual environment
    python3 -m venv owl_env
    source owl_env/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install requirements
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
    else
        log_error "requirements.txt not found! Make sure you're in the OWL directory."
        exit 1
    fi
    
    # Install Jetson-specific requirements
    if [ -f "jetson_requirements.txt" ]; then
        pip install -r jetson_requirements.txt
    else
        log_warning "jetson_requirements.txt not found. Installing basic Jetson dependencies..."
        pip install Jetson.GPIO psutil
    fi
    
    log_success "Python environment configured"
}

# Configure GPIO permissions
setup_gpio_permissions() {
    log_info "Configuring GPIO permissions..."
    
    # Add user to gpio group
    sudo usermod -a -G gpio $USER
    
    # Create udev rules
    echo 'SUBSYSTEM=="gpio", KERNEL=="gpiochip[0-9]", GROUP="gpio", MODE="0660"' | sudo tee /etc/udev/rules.d/99-gpio.rules > /dev/null
    
    # Reload udev rules
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    
    log_success "GPIO permissions configured"
    log_warning "You may need to log out and back in for group changes to take effect"
}

# Test camera
test_camera() {
    log_info "Testing CSI camera..."
    
    # Test CSI camera 0
    if gst-launch-1.0 nvarguscamerasrc sensor-id=0 num-buffers=10 ! fakesink 2>/dev/null; then
        log_success "CSI camera detected and working"
    else
        log_warning "CSI camera test failed. You may need to connect a CSI camera or use USB camera."
    fi
}

# Verify OpenCV with GStreamer
verify_opencv() {
    log_info "Verifying OpenCV installation..."
    
    source owl_env/bin/activate
    
    python3 -c "
import cv2
print(f'OpenCV version: {cv2.__version__}')
build_info = cv2.getBuildInformation()
gst_support = 'GStreamer' in build_info and 'YES' in build_info[build_info.find('GStreamer'):build_info.find('GStreamer')+100]
print(f'GStreamer support: {gst_support}')
if not gst_support:
    print('WARNING: OpenCV may not have GStreamer support. CSI cameras may not work properly.')
" 2>/dev/null || log_warning "Could not verify OpenCV installation"
}

# Enable performance mode
enable_performance_mode() {
    read -p "Enable maximum performance mode? This increases power consumption. (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Enabling maximum performance mode..."
        
        # Enable jetson_clocks if available
        if command -v jetson_clocks &> /dev/null; then
            sudo jetson_clocks
            log_success "jetson_clocks enabled"
        fi
        
        # Set power mode to maximum
        if command -v nvpmodel &> /dev/null; then
            sudo nvpmodel -m 0 2>/dev/null || log_warning "Could not set maximum power mode"
            log_success "Maximum power mode set"
        fi
    else
        log_info "Skipping performance mode setup"
    fi
}

# Create example configuration
create_example_config() {
    log_info "Creating example configuration..."
    
    # Detect Jetson model and create appropriate config
    MODEL=$(cat /proc/device-tree/model 2>/dev/null | tr -d '\0')
    
    if [[ $MODEL == *"Orin Nano"* ]]; then
        if [ -f "config/JETSON_ORIN_NANO_SUPER.ini" ]; then
            cp config/JETSON_ORIN_NANO_SUPER.ini config/jetson_config.ini
            log_success "Created jetson_config.ini based on Orin Nano Super template"
        fi
    else
        if [ -f "config/JETSON_POWER_EFFICIENT.ini" ]; then
            cp config/JETSON_POWER_EFFICIENT.ini config/jetson_config.ini
            log_success "Created jetson_config.ini based on power efficient template"
        fi
    fi
}

# Main installation function
main() {
    echo "=================================================="
    echo "  OpenWeedLocator Jetson Setup Script"
    echo "  For NVIDIA Jetson Orin Nano Super & other Jetson devices"
    echo "=================================================="
    echo
    
    # Check if we're on a Jetson device
    check_jetson
    
    # Check JetPack version
    check_jetpack
    
    echo
    log_info "Starting OWL setup for Jetson..."
    
    # Install dependencies
    install_system_deps
    install_jetson_gpio
    
    # Setup Python environment
    setup_python_env
    
    # Configure GPIO
    setup_gpio_permissions
    
    # Test camera
    test_camera
    
    # Verify OpenCV
    verify_opencv
    
    # Create example config
    create_example_config
    
    # Optional performance mode
    enable_performance_mode
    
    echo
    log_success "OWL Jetson setup completed!"
    echo
    echo "Next steps:"
    echo "1. Log out and back in to apply GPIO group changes"
    echo "2. Activate the virtual environment: source owl_env/bin/activate"
    echo "3. Test OWL: python owl.py --show-display"
    echo "4. For high performance: use config/JETSON_HIGH_PERFORMANCE.ini"
    echo "5. For power efficiency: use config/JETSON_POWER_EFFICIENT.ini"
    echo
    echo "For more information, see the Jetson installation section in README.md"
}

# Run main function
main "$@"