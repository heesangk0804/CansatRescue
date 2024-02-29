# RaspPiSetup for Developing CanSat Constellation Rescue System

## 1. Basic Tools
: Update and install basic tools, libraries

> sudo apt upgrade
> 
> sudo apt install vim
>
> sudo apt install python3

## 2. Swap Memory Setting
: Spare extra memory for RAM by swapping some from SD Card

* Check current memory/swap size
> free -h
* Check SD Card(disk) size
> df -h
* Modify swap size by accessing dphs-swapfile
> vi /etc/dphys-swapfile
>> ...
>>
>> CONF_SWAPFILE=/home/pi &nbsp;&nbsp;&nbsp; #location of swap file
>> 
>> CONF_SWAPSIZE=2048 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; #size of swap
>>
>> ...
* Restart the dphs-swapfile
> service dphys-swapfile restart

## 3. Linux Kernel Header
: Install linux kernel header to add modules to kernel, perform system call, etc

* Install kernel header if not
> sudo apt install linux-kernel-headers
* Check if kernel header successfully installed, with proper version
> /usr/src $ ls
> 
> /usr/src $ uname -r

## 4. Setup for Wifi Connection, LAN Card Drivers
* Fixed IP Settings for convenience in ssh remote access
> vi /etc/dhcpcd.conf
>> ...
>>
>> interface wlan0
>>
>> static ip_address=192.168.**255.XX**/24 &nbsp;&nbsp;&nbsp; #fixed local IP address for Pi
>>  
>> static routers=192.168.**255.1**/24 &nbsp;&nbsp;&nbsp; #IP address of gateway server
>> 
>> ...

* Install drivers for unsupported Wi-Fi LAN Cards (ex: RealTek LANs)
> git clone https://github.com/morrownr/88x2bu-20210702 &nbsp;&nbsp;&nbsp; #88x2bu LAN driver
>
> git clone https://github.com/morrownr/8821cu-20210916 &nbsp;&nbsp;&nbsp; #8821cu LAN driver
>
> cd ~/**(driver directory)**
>
> sudo ./install-driver.sh

## 5. Setup for Serial Communications
: install libraries to control serial connected peripherals from python code
* Install smbus for i2c control
> sudo pip3 install smbus2
* Install driver for bme280 sensor
> sudo pip3 install RPi.bme280
* Install pynmea library for parsing GPS data
> sudo pip3 install pynmea2

## 6. Setup for Camera Streaming
: install libraries for camera control and streaming
* install libcamera for camera control (unnecessary; already included in default packages
> sudo apt install libcamera-apps
* install vlc for rtsp streaming the video
> sudo apt install vlc

## 6. Setup for Ad-Hoc Mesh Network
: adjusting WLAN interface settings, adding **'batman-adv'** driver module to set up an ad-hoc mesh network
reference: https://github.com/binnes/WiFiMeshRaspberryPi/blob/master/part1/README.md

* (1) Change the wlan module setting to ad-hoc
> vi /etc/network/interfaces.d/wlan0
>> auto wlan0
>> 
>> iface wlan0 inet manual
>> 
>> &nbsp;&nbsp;&nbsp; wireless-channel 1	&nbsp;&nbsp;&nbsp;	#channel num among 2.4G band
>>
>> &nbsp;&nbsp;&nbsp; wireless-essid cansat-mesh &nbsp;&nbsp;&nbsp; #name for network
>>
>> &nbsp;&nbsp;&nbsp; wireless-mode ad-hoc &nbsp;&nbsp;&nbsp; #set as ad-hoc


