# RaspPiSetup for Developing CanSat Constellation Rescue System

## 1. Basic Tools
: Update and install basic tools, libraries

> sudo apt upgrade
> 
> sudo apt install vim
>
> sudo apt install python3
* List&find installed packages
> apt list #--installed
>
> apt search **package_name**

## 2. Swap Memory Setting
: Spare extra memory for RAM by swapping some from SD Card

* Check current memory/swap size
> free -h
* Check SD Card(disk) size
> df -h
* Modify swap size by accessing dphs-swapfile
> sudo vi /etc/dphys-swapfile
>> ...
>>
>> CONF_SWAPFILE=/home/pi/ &nbsp;&nbsp;&nbsp; #location of swap file
>> 
>> CONF_SWAPSIZE=2048 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; #size of swap
>>
>> ...
* Restart the dphs-swapfile
> service dphys-swapfile restart

## 3. Linux Kernel Header
: Install linux kernel header to add modules to kernel, perform system call, etc

* Install kernel header if not
> sudo apt install linux-headers
* Check if kernel header successfully installed, with proper version
> /usr/src $ ls
> 
> /usr/src $ uname -r

## 4. Setup for Wifi Connection, LAN Card Drivers
* Enable ssh after reboot 
> sudo systemctl enable ssh
* Enable realvnc after reboot 
> sudo systemctl enable vncserver-x11-serviced.service
* Install xrdp server & enable xrdp after reboot 
> sudo apt install xrdp
> sudo systemctl enable xrdp 

* Fixed IP Settings for convenience in ssh remote access
> netstat -nr
> 
> sudo vi /etc/dhcpcd.conf
>> ...
>>
>> interface wlan0
>>
>> static ip_address=192.168.**252.XX**/24 &nbsp;&nbsp;&nbsp; #fixed local IP address for Pi
>>  
>> static routers=192.168.**252.1** &nbsp;&nbsp;&nbsp; #IP address of gateway server
>> 
>> ...

* Install drivers for unsupported Wi-Fi LAN Cards (ex: RealTek LANs)
> git clone https://github.com/morrownr/88x2bu-20210702 &nbsp;&nbsp;&nbsp; #88x2bu LAN driver
>
> git clone https://github.com/morrownr/8821cu-20210916 &nbsp;&nbsp;&nbsp; #8821cu LAN driver
>
> cd ~/**(driver directory)**
>
> echo 'denyinterfaces wlan0' | sudo tee --append /etc/dhcpcd.conf
> sudo ./install-driver.sh

* Wifi Connection Setting through Terminal
> sudo vi /etc/wpa_supplicant/wpa_supplicant.conf
>> ...
>>
>> network={
>>
>>   ssid=**"WiFi_Network_Name"** 
>>
>>   psk=**"password"**    #key_mgmt=NONE  -> if no password
>>
>>   priority=**N**
>>
>>   #id_str=**"Network_ID"**
>>
>> }
> sudo ifdown wlan1
>
> sudo ifup wlan1


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
* Disable legacy camera setting from raspi-config, since libcamera library doesn't support it
* 
* install libcamera for camera control (unnecessary; already included in default packages
> sudo apt install libcamera-apps
* install vlc for rtsp streaming the video
> sudo apt install vlc
* Create shell script for camera control & streaming, then execute it every time the system boots
> vi ~/start-libcamera-rtsp.sh
>> #!/bin/bash
>> 
>> libcamera-vid -t 0 --inline -n -o - | cvlc -vvv stream:////dev/stdin --sout '#rtp{sdp=rtsp://:8080/}' :demux=h264
>
> chmod +x ~/start-libcamera-rtsp.sh
>
> sudo vi /etc/rc.local
>> ...
>>
>> su - **USERNAME** -c '/home/**USERNAME**/start-libcamera-rtsp.sh' &
>>
>> ...
* libcamera commands for camera control
> libcamera-hello  &nbsp;&nbsp;&nbsp; #starts the camera, displays a preview window
>
> libcamera-jpeg  &nbsp;&nbsp;&nbsp; #simple still image capture application with avoiding some of the additional features
>
> libcamera-still -o **(filename)**.jpg &nbsp;&nbsp;&nbsp; #still image capture application with supporting more of the legacy raspistill options
>
>  libcamera-still -t 5000 --datetime -n --timelapse 1000 &nbsp;&nbsp;&nbsp; #Continuous automatic photo taking, 1 shot per second within 5 seconds
>
> libcamera-vid -t 10000 -o **(filename)**.h264 &nbsp;&nbsp;&nbsp; #Video capture application by H.264 encoder; duration = 10000 ms
>
> libcamera-raw -t 2000 -o **(filename)**.raw  &nbsp;&nbsp;&nbsp; #Video recording w/ raw Bayer frames directly from the sensor;no preview window
>
> libcamera-XXX --help &nbsp;&nbsp;&nbsp; #Instructions for more features
>

## 7. Setup for Ad-Hoc Mesh Network
: adjusting WLAN interface settings, adding **'batman-adv'** driver module, running execution files to set up an ad-hoc mesh network

reference: https://github.com/binnes/WiFiMeshRaspberryPi/blob/master/part1/README.md

* i. WLAN Interface Settings

i-(1). Change the wlan2 interface mode into Ad-Hoc
> sudo vi /etc/network/interfaces.d/wlan1
>> auto wlan1
>> 
>> iface wlan1 inet manual
>> 
>> &nbsp;&nbsp;&nbsp; wireless-channel 1	&nbsp;&nbsp;&nbsp;	#channel num among 2.4G band
>>
>> &nbsp;&nbsp;&nbsp; wireless-essid cansat-mesh &nbsp;&nbsp;&nbsp; #name for network
>>
>> &nbsp;&nbsp;&nbsp; wireless-mode ad-hoc &nbsp;&nbsp;&nbsp; #set as ad-hoc

i-(2). Block the wlan1 interface from Dymanic IP Allocation (DHCP) from network 
> echo 'denyinterfaces wlan1' | sudo tee --append /etc/dhcpcd.conf

< Additional Settings for Gateway >

i-(3). Make gateway server to dynamically allocate IP to its clients
> sudo apt install -y dnsmasq
> 
> sudo vi /etc/dnsmasq.conf
>> interface=bat0
>>
>> dhcp-range=192.168.199.2,192.168.199.99,255.255.255.0,12h

* ii 'batman-adv' Driver Presettings

ii-(1). Set 'batman-adv' kernel driver module to be loaded every time the system boots
> echo 'batman-adv' | sudo tee --append /etc/modules
>
> lsmod &nbsp;&nbsp;&nbsp; #check if batman module properly added

ii-(2). Install batctl utility to control batman-adv
>sudo apt install -y batctl

* iii. Create & Run shell script exe program to run mesh network

iii-(1). Write shell script file to run mesh network (node client version)
> vi ~/start-batman-adv.sh
>> #!/bin/bash
>>
>> #batman-adv interface to use
>>
>> sudo batctl if add wlan1
>>
>> sudo ifconfig bat0 mtu 1468
>>
>> #Tell batman-adv this is a gateway client
>> 
>> sudo batctl gw_mode client
>>
>> #Activates batman-adv interfaces
>>
>> #In case of wlan0 distraction:disable wlan0(on-chip broadcom)
>> 
>> #sudo ifconfig wlan0 down
>> 
>> sudo ifconfig wlan1 up
>>
>> sudo ifconfig bat0 up
>>
>> sudo ifconfig bat0 192.168.199.**X**/24 #Fixed IP

iii-(1). Write shell script file to run mesh network (gateway version)
> vi ~/start-batman-adv.sh
>> #!/bin/bash
>>
>> #batman-adv interface to use
>>
>> sudo batctl if add wlan1
>>
>> sudo ifconfig bat0 mtu 1468
>>
>> #Tell batman-adv this is an internet gateway
>>
>> sudo batctl gw_mode server
>>
>> #Enable port forwarding
>>
>> sudo sysctl -w net.ipv4.ip_forward=1
>>
>> sudo iptables -t nat -A POSTROUTING -o wlan2 -j MASQUERADE
>>
>> sudo iptables -A FORWARD -i wlan2 -o bat0 -m conntrack –ctstate RELATED,ESTABLISHED -j ACCEPT
>>
>> sudo iptables -A FORWARD -i bat0 -o wlan2 -j ACCEPT
>>
>> #Activates batman-adv interfaces
>>
>> #In case of wlan0 distraction:disable wlan0(on-chip broadcom)
>> 
>> #sudo ifconfig wlan0 down
>>
>> sudo ifconfig wlan1 up
>>
>> sudo ifconfig bat0 up
>>
>> sudo ifconfig bat0 192.168.199.**N**/24


iii-(2). Make the file executable, then let it run every time the system boots
> chmod +x ~/start-batman-adv.sh
>
> sudo vi /etc/rc.local
>> ...
>>
>> /home/**USERNAME**/start-batman-adv.sh &
>>
>> ...
>> exit 0
>
> sudo reboot

## 8. Setup for Each Node to Create Wireless Access Point Server
* Install hostapd package: Daemon for controlling Wi-Fi AP server
> sudo apt install -y hostapd 
>
> sudo systemctl unmask hostapd
>
* (prepared through #7) Install DHCP package: Daemon for dynamic IP allocation(DHCP) to clients

(Dynamic IP allocation could be also done by isc-dhcp-server software instead of dnsmasq)
> sudo apt install -y dnsmasq
* Temorarily stop hostapd&dnsmasq
> sudo systemctl stop hostapd
>
> sudo systemctl stop dnsmasq
* Edit dhcpcd configuration file
> sudo vi /etc/dhcpcd.conf
>> interface wlan2
>>
>> static ip_address=192.168.**(SatNum)**.1/24
>>
>> nohook wpa_supplicant
>
> sudo service dhcpcd restart
* Edit dnsmasq configuration file to set DHCP allocation
> sudo vi /etc/dnsmasq.conf
>> interface=wlan2
>>
>> dhcp-range=192.168.2.2,192.168.2.20,255.255.255.0,24h
* Edit hostapd configuration file for WiFi AP Server basic settings:
> sudo vi /etc/hostapd/hostapd.conf
>> interface=wlan2
>>
>> driver=nl80211
>>
>> ssid=**(AP server name)**
>>
>> hw_mode=g
>>
>> channel=7
>>
>> wmm_enabled=0
>>
>> macaddr_acl=0
>>
>> auth_algs=1
>>
>> ignore_broadcast_ssid=0
>>
>> wpa=2
>>
>> wpa_passphrase=**(AP Server password)**
>>
>> wpa_key_mgmt=WPA-PSK
>>
>> wpa_pairwise=TKIP
>>
>> rsn_pairwise=CCMP
* Edit hostapd to inform daemon with the hostapd.conf file
> sudo vi /etc/default/hostapd
>
> DAEMON_CONF="/etc/hostapd/hostapd.conf"
* Reboot and start both daemon hostapd, dnsmasq
> sudo reboot
>
> sudo systemctl start hostapd
>
> sudo systemctl start dnsmasq
* Port Forwarding, Masking options (Unnecessary for AP server in this project)
> vi ~/wifi-ap-forwarding.sh
>> sudo sysctl -w net.ipv4.ip_forward=1
>>
>> sudo iptables -t nat -A POSTROUTING -o wlan1 -j MASQUERADE
>>
>> #sudo sh -c "iptables-save > /etc/iptables.ipv4.nat"
>>
> chmod +x ~/wifi-ap-forwarding.sh
>
>  sudo vi /etc/rc.local
>> ...
>> 
>> /home/**USERNAME**/wifi-ap-forwarding.sh &
>> 
>> #iptables-restore < /etc/iptables.ipv4.nat
>>
>> sudo systemctl start hostapd
>>
>> ...

reference: https://wikidocs.net/78532

## 9. RIP Routing Setting between mesh network and each AP server
* Install quagga package:  network routing software for UNIX platforms, providing various routing protocols including OSPF, RIP, BGP, IS-IS, etc.
> sudo apt install -y quagga
* Set configurations for zebra, a core daemon of quagga

The zebra daemon presents the Zserv API over a socket to Quagga clients. 

The Zserv clients each implement certain routing protocols and communicate routing updates to zebra
> sudo vi /etc/quagga/zebra.conf
>>
>> hostname Router
>>
>> password zebra
>>
>> enable password zebra
>>
>> debug zebra events
>>
>> debug zebra packet
>>
>> ip forwarding
>>
>> log file /var/log/quagga/zebra.log
* Set configurations for ripd, a Zserv client for Routing Information Protocol (RIP)

RIP: a distance-vector routing protocols which determines the optimal routing path by minimum number of hop counts
> sudo vi /etc/quagga/ripd.conf
>> hostname ripd
>>
>> password zebra
>>
>> debug rip events
>>
>> debug rip packet
>>
>> router rip
>>
>>  version 2
>>
>> ! Network address of AP server network
>> 
>> network 192.168.**N**.0/24
>>
>> ! Network address of CanSat mesh network
>> 
>> network 192.168.199.0/24
>>
>> log file /var/log/quagga/ripd.log
* Restart quagga zebra, ripd daemon
> sudo service zebra restart
>
> sudo service ripd restart

## 10. PI thread management
* Find currently running process in specific port(<PORTADDR>)
> sudo lsof -i :**(PORTADDR)**
>> (Result)
>>
>> COMMAND  PID       USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
>>
>> python3 1429 heesangkim   10u  IPv4  50816      0t0  TCP 192.168.1.1:webmin (LISTEN)
* Manually kill currently running process with <PID>
> kill -9 **(PID)**

## Appendix
* +Commands to check network connenction
> ifconfig  &nbsp;&nbsp;&nbsp; #configure ip address, packets of each interfaces
>
> netstat  &nbsp;&nbsp;&nbsp; #configure every network connenction(Internet+Internal domain)
>
> iwconfig  &nbsp;&nbsp;&nbsp; #configure wireless interface settings, information
>
> ping  &nbsp;&nbsp;&nbsp; #check if external IP accessable through network
>
> sudo batctl n &nbsp;&nbsp;&nbsp; #check external IP devices(nodes) in mesh network
> 
> sudo batctl if &nbsp;&nbsp;&nbsp; #check mesh network active
>
> netstat -r  &nbsp;&nbsp;&nbsp; #configure gateway ip address
>
> route  &nbsp;&nbsp;&nbsp; #configure gateway ip address
>
> nmap -sn **(your host IP)**/24   &nbsp;&nbsp;&nbsp; #configure all the hosts' IPs connected to local network
>> (Installation of nmap)
>>
>> sudo apt install -y snapd
>>
>> sudo reboot
>>
>> sudo snap install -y core
>>
>> sudo snap install -y nmap
>
> ssh **(host ID)**@**(IP Address)**  #remote access to another device in network, through shell script
>
> sudo ifconfig wlan**N** down  # disable certain wlan interface temporarily
>
> lsusb #list of usb devices
> 
> lsmod #list of kernel modules loaded in memory
>
> lsof #list of currently open files


