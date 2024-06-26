#!/usr/bin/env python
# license removed for brevit
import rclpy
from rclpy.node import Node
import serial
import time
import argparse

from serial import SerialException
from msgfolder.msg import MachineStatus
from std_msgs.msg import *

class MachineNode(Node):
    def __init__(self):
        super().__init__('machine_node')
        self.status = MachineStatus()
        self.declare_parameters(
            namespace='',
            parameters=[
                ('sim_port', True),
                ('port', '/dev/ttyUSB0'),
                ('path', '/media/gcode/'),
                ('cultivation_interval', 120)
            ]
        )
        self.pubMachineStatus = self.create_publisher(MachineStatus, 'LOMAS_MachineState', 10)
        self.sub_cmd = self.create_subscription(UInt8, 'LOMAS_MachineCmd', self.cmdCallback, 10)
        self.sub_stop = self.create_subscription(Bool, 'LOMAS_MachineStop', self.stopCallback, 10)
        self.sub_abort = self.create_subscription(Bool, 'LOMAS_MachineAbort', self.abortCallback, 10)
        self.sub_intervall = self.create_subscription(UInt8, 'LOMAS_MachineSetIntervall', self.intervallCallback, 10)

        self.status.error_nr = 99
        self.stop = False
        self.abort = False

    def loadParameters(self):
        self.IsInSimMode = self.get_parameter('sim_port').value
        self.port = self.get_parameter('port').value
        self.path = self.get_parameter('path').value
        self.status.interval = self.get_parameter('cultivation_interval').value

        self.get_logger().info('Machine param values:')
        self.get_logger().info(f" * IsInSimMode: {self.IsInSimMode}")
        self.get_logger().info(f" * Port: {self.port}")
        self.get_logger().info(f" * Path: {self.path}")
        self.get_logger().info(f" * Interval: {self.status.interval}")

        self.pubMachineStatus.publish(self.status)


    def removeComment(string):
        if (string.find(';') == -1):
            return string
        else:
            return string[:string.index(';')]

    def connectToMachine(self):

        self.get_logger().info('Opening Serial Port')
        if self.IsInSimMode:
            self.get_logger().info('Warning : Serial port will be simulated')
            self.status.error_nr = 0
        else:
            try:
                self.s = serial.Serial(self.port, 115200)
                self.s.write(b"\r\n\r\n")  # Hit enter a few times to wake the robot
                time.sleep(2)  # Wait for machine to initialize
                self.s.flushInput()  # Flush startup text in serial input
                self.status.error_nr = 0
                self.get_logger().info('Serial port connected to machine')
            except serial.SerialException:
                self.status.error_nr = 98
                self.get_logger().error('Error when opening Serial Port')

        self.pubMachineStatus.publish(self.status)

    def sendSerialCmd(self, cmd):
        IsInSimMode = self.get_parameter('sim_port').value
        if IsInSimMode:
            grbl_out = 'oMGok\n'
        else:
            self.ser.write(cmd)  # Send g-code block
            grbl_out = self.ser.readline()  # Wait for response with carriage return

        self.get_logger().info(f': {grbl_out.strip()}')

        if grbl_out == 'oMGok\n':
            return True
        else:
            return False

    def sendGCodeFile(self, file, seq):
        self.status.sequense_started = True
        self.status.machine_moving = True
        self.stop = False
        self.abort = False
        self.pubMachineStatus.publish(self.status)

        try:
            with open(file, 'r') as f:
                self.get_logger().info(f'Opening gcode file: {file}')
                for line in f:
                    l = self.remove_comment(line)
                    l = l.strip()  # Strip all EOL characters for streaming
                    if not l.isspace() and len(l) > 0:
                        ok = self.sendSerialCmd((l + '\n'))

                    if self.stop:
                        self.get_logger().info('Stopped')
                        self.status.sequense_nr = 90
                        self.status.MachineMoving = False
                        self.pubMachineStatus.publish(self.status)
                        while self.stop:
                            if self.abort:
                                self.status.sequense_nr = 91
                                self.get_logger().info('Aborting while')
                                self.pubMachineStatus.publish(self.status)
                                break

                            time.sleep(0.1)

                        self.get_logger().info('Restarted')
                        self.status.machine_moving = True
                        self.status.sequense_nr = seq
                        self.pubMachineStatus.publish(self.status)

                    if self.abort:
                        self.status.sequense_nr = 91
                        self.pubMachineStatus.publish(self.status)
                        self.get_logger().info('Aborting for')
                        break

        except FileNotFoundError:
            self.get_logger().error(f"Error: File {file} not found")

        # f.close()????
        self.status.error_nr = 0
        self.status.sequense_started = False
        self.status.machine_moving = False
        self.status.sequense_nr = 0
        self.abort = False

    def sendGCodeCmd(self, cmd):
        self.status.sequense_started = True
        self.status.machine_moving = True
        self.status.sequense_nr = 99
        self.pubMachineStatus.publish(self.status)

        ok = self.sendSerialCmd((cmd + '\n'))

        if ok:
            self.status.error_nr = 0
            self.status.sequense_started = False
            self.status.machine_moving = False
            self.status.sequense_nr = 0

    def stopCallback(self, data):
        self.get_logger().info('Stop')
        self.stop = data.data

    def abortCallback(self, data):
        self.get_logger().info('Abort')
        self.abort = data.data

    def intervallCallback(self, data):
        self.get_logger().info(f'Set interval: {data.data}')
        self.status.interval = data.data
        self.setParameters([rclpy.parameter.Parameter('cultivation_interval', rclpy.Parameter.Type.INTEGER, data.data)])
        self.pubMachineStatus.publish(self.status)

    def cmdCallback(self, data):
        self.get_logger().info(f'Received command: {data.data}')
        if data.data == 99:
            self.get_logger().info('Starting to home robot')
            self.status.is_synced = False
            self.sendGCodeCmd('G28 X Y Z')
            self.status.is_synced = True
        elif data.data == 1:
            self.get_logger().info('Send cultivation.g file')
            self.status.sequense_nr = 1
            self.sendGCodeFile(path + 'cultivation.g', 1)
        elif data.data == 2:
            self.get_logger().info('Send seed.g file')
            self.status.sequense_nr = 2
            self.sendGCodeFile(path + 'seed.g', 2)
        elif data.data == 90:
            self.get_logger().info('Man. pos X')
            self.sendGCodeCmd('G91\n'+'G0 X10 F1000\n')
            self.get_logger().info('G0 X10 F1000\n')
        elif data.data == 91:
            self.get_logger().info('Man. neg X')
            self.sendGCodeCmd('G91\n'+'G0 X-10 F1000\n')
            self.get_logger().info('G0 X-10 F1000\n')
        elif data.data == 92:
            self.get_logger().info('Man. pos Y')
            self.sendGCodeCmd('G91\n'+'G0 Y10 F1000\n')
            self.get_logger().info('G0 Y10 F1000\n')
        elif data.data == 93:
            self.get_logger().info('Man. neg Y')
            self.sendGCodeCmd('G91\n'+'G0 Y-10 F1000\n')
            self.get_logger().info('G0 Y-10 F1000\n')
        elif data.data == 94:
            self.get_logger().info('Man. pos X pos Y')
            self.sendGCodeCmd('G91\n'+'G0 X10 Y10 F1000\n')
            self.get_logger().info('G0 X10 Y10 F1000\n')
        elif data.data == 95:
            self.get_logger().info('Man. neg X pos Y')
            self.sendGCodeCmd('G91\n'+'G0 X-10 Y10 F1000\n')
            self.get_logger().info('G0 X-10 Y10 F1000\n')
        elif data.data == 96:
            self.get_logger().info('Man. pos X neg Y')
            self.sendGCodeCmd('G91\n'+'G0 X10 Y-10 F1000\n')
            self.get_logger().info('G0 X10 Y-10 F1000\n')
        elif data.data == 97:
            self.get_logger().info('Man. neg X neg Y')
            self.sendGCodeCmd('G91\n'+'G0 X-10 Y-10 F1000\n')
            self.get_logger().info('G0 X-10 Y-10 F1000\n')

        self.pubMachineStatus.publish(self.status)



def main(args=None):
    rclpy.init(args=args)
    machine_node = MachineNode()
    try:
        rclpy.spin(machine_node)
    except KeyboardInterrupt:
        pass
    finally:
        machine_node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()