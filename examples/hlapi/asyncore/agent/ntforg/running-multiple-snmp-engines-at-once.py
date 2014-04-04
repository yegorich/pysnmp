#
# Notification Originator
#
# Send SNMP notifications in behalf of multiple independend SNMP engines 
# using the following options:
#
# * with a single transport dispatcher and two independent SNMP engines
# * SNMPv2c and SNMPv3
# * with community name 'public' or USM username usr-md5-des
# * over IPv4/UDP
# * send IMFORM notification
# * to multiple Managers
# * with TRAP ID 'coldStart' specified as a MIB symbol
# * include managed object information specified as var-bind objects pair
#
# Within this script we have a single asynchronous TransportDispatcher
# and a single UDP-based transport serving two independent SNMP engines.
# We use a single instance of AsyncNotificationOriginator with each of 
# SNMP Engines to communicate INFORM notification to remote systems.
#
# When we receive a [response] message from remote system we use
# a custom message router to choose what of the two SNMP engines
# data packet should be handed over. The selection criteria we
# employ here is based on peer's UDP port number. Other selection
# criterias are also possible.
# 
from pysnmp.entity.rfc3413.oneliner import ntforg
from pysnmp.entity import engine
from pysnmp.entity.rfc3413 import context
from pysnmp.carrier.asynsock.dispatch import AsynsockDispatcher
from pysnmp.proto import rfc1902

# List of targets in the following format:
# ( ( authData, transportTarget ), ... )
targets = (
    # 1-st target (SNMPv2c over IPv4/UDP)
    ( ntforg.CommunityData('public'),
      ntforg.UdpTransportTarget(('localhost', 1162)) ),
    # 2-nd target (SNMPv3 over IPv4/UDP)
    ( ntforg.UsmUserData('usr-md5-des', 'authkey1', 'privkey1'),
      ntforg.UdpTransportTarget(('localhost', 162)) )
)

def cbFun(snmpEngine, sendRequestHandle, errorIndication, 
          errorStatus, errorIndex, varBinds, cbCtx):
    snmpEngine = cbCtx
    if errorIndication:
        print('Notification %s for %s not sent: %s' % (sendRequestHandle, snmpEngine.snmpEngineID.prettyPrint(), errorIndication))
    elif errorStatus:
        print('Notification Receiver returned error for request %s, SNMP Engine %s: %s @%s' % (sendRequestHandle, snmpEngine.snmpEngineID.prettyPrint(), errorStatus, errorIndex))
    else:
        print('Notification %s for SNMP Engine %s delivered:' % (sendRequestHandle, snmpEngine.snmpEngineID.prettyPrint()))
        for name, val in varBinds:
            print('%s = %s' % (name.prettyPrint(), val.prettyPrint()))

# Instantiate the single transport dispatcher object
transportDispatcher = AsynsockDispatcher()

# Setup a custom data routing function to select snmpEngine by transportDomain
transportDispatcher.registerRoutingCbFun(
    lambda td,ta,d: ta[1] % 3 and 'A' or 'B'
)

snmpEngineA = engine.SnmpEngine()
snmpEngineA.registerTransportDispatcher(transportDispatcher, 'A')

snmpEngineB = engine.SnmpEngine()
snmpEngineB.registerTransportDispatcher(transportDispatcher, 'B')

ntfOrg = ntforg.AsyncNotificationOriginator()

for authData, transportTarget in targets:
    snmpEngine = transportTarget.getTransportInfo()[1][1] % 3 and \
            snmpEngineA or snmpEngineB
    sendPduHandle = ntfOrg.sendNotification(
        snmpEngine,
        context.SnmpContext(snmpEngine),
        authData,
        transportTarget,
        'inform',
        ntforg.MibVariable('SNMPv2-MIB', 'coldStart'),
        ( ( rfc1902.ObjectName('1.3.6.1.2.1.1.1.0'),
            rfc1902.OctetString('my name') ), ),
        cbInfo=(cbFun, snmpEngine)
    )

transportDispatcher.runDispatcher()