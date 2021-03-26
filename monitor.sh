#!/usr/bin/bash
#
# Sample basic monitoring functionality; Tested on Amazon Linux 2
#
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
MEMORYUSAGE=$(free -m | awk 'NR==2{printf "%.2f%%", $3*100/$2 }')
CPU_USAGE=$(vmstat | awk 'NR==3{print 100-$15"%"}') #this is my addition, uses vmstat and calculates cpu usage by taking the cpu idle time away from 100pc 
UPTIME=$(uptime |awk '{ print $3 $4 }')
PROCESSES=$(expr $(ps -A | grep -c .) - 1)
HTTPD_PROCESSES=$(ps -A | grep -c httpd) 

echo " "
echo " Instance Monitoring Data "
echo "--------------------------"
echo "Instance ID: $INSTANCE_ID"
echo "Uptime: $UPTIME"
echo "CPU USAGE SNAPSHOT: $CPU_USAGE"
echo "Memory utilisation: $MEMORYUSAGE"
echo "No of processes: $PROCESSES"
if [ $HTTPD_PROCESSES -ge 1 ]
then
    echo "Web server is running"
else
    echo "Web server is NOT running"
fi
echo " "
