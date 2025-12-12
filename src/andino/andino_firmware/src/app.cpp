// Code in this file is inspired by:
// https://github.com/hbrobotics/ros_arduino_bridge/blob/indigo-devel/ros_arduino_firmware/src/libraries/ROSArduinoBridge/ROSArduinoBridge.ino
//
// ----------------------------------------------------------------------------
// ros_arduino_bridge's license follows:
//
// Software License Agreement (BSD License)
//
// Copyright (c) 2012, Patrick Goebel.
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions
// are met:
//
//   * Redistributions of source code must retain the above copyright
//     notice, this list of conditions and the following disclaimer.
//   * Redistributions in binary form must reproduce the above
//     copyright notice, this list of conditions and the following
//     disclaimer in the documentation and/or other materials provided
//     with the distribution.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
// "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
// LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
// FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
// COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
// INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
// BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
// LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
// CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
// LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
// ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
// POSSIBILITY OF SUCH DAMAGE.

// BSD 3-Clause License
//
// Copyright (c) 2023, Ekumen Inc.
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are met:
//
// 1. Redistributions of source code must retain the above copyright notice, this
//    list of conditions and the following disclaimer.
//
// 2. Redistributions in binary form must reproduce the above copyright notice,
//    this list of conditions and the following disclaimer in the documentation
//    and/or other materials provided with the distribution.
//
// 3. Neither the name of the copyright holder nor the names of its
//    contributors may be used to endorse or promote products derived from
//    this software without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
// AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
// DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
// FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
// DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
// SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
// CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
// OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#include "app.h"

#include "I2Cdev.h"
#include "MPU6050.h"
#include <Arduino.h>
#include <Wire.h>


#include "commands.h"
#include "constants.h"
#include "digital_out_arduino.h"
#include "encoder.h"
#include "hw.h"
#include "interrupt_in_arduino.h"
#include "motor.h"
#include "pid.h"
#include "pwm_out_arduino.h"
#include "serial_stream_arduino.h"
#include "shell.h"

namespace andino {

SerialStreamArduino App::serial_stream_;

Shell App::shell_;

DigitalOutArduino App::left_motor_enable_digital_out_(Hw::kLeftMotorEnableGpioPin);
PwmOutArduino App::left_motor_forward_pwm_out_(Hw::kLeftMotorForwardGpioPin);
PwmOutArduino App::left_motor_backward_pwm_out_(Hw::kLeftMotorBackwardGpioPin);
Motor App::left_motor_(&left_motor_enable_digital_out_, &left_motor_forward_pwm_out_,
                       &left_motor_backward_pwm_out_);

DigitalOutArduino App::right_motor_enable_digital_out_(Hw::kRightMotorEnableGpioPin);
PwmOutArduino App::right_motor_forward_pwm_out_(Hw::kRightMotorForwardGpioPin);
PwmOutArduino App::right_motor_backward_pwm_out_(Hw::kRightMotorBackwardGpioPin);
Motor App::right_motor_(&right_motor_enable_digital_out_, &right_motor_forward_pwm_out_,
                        &right_motor_backward_pwm_out_);

InterruptInArduino App::left_encoder_channel_a_interrupt_in_(Hw::kLeftEncoderChannelAGpioPin);
InterruptInArduino App::left_encoder_channel_b_interrupt_in_(Hw::kLeftEncoderChannelBGpioPin);
Encoder App::left_encoder_(&left_encoder_channel_a_interrupt_in_,
                           &left_encoder_channel_b_interrupt_in_);

InterruptInArduino App::right_encoder_channel_a_interrupt_in_(Hw::kRightEncoderChannelAGpioPin);
InterruptInArduino App::right_encoder_channel_b_interrupt_in_(Hw::kRightEncoderChannelBGpioPin);
Encoder App::right_encoder_(&right_encoder_channel_a_interrupt_in_,
                            &right_encoder_channel_b_interrupt_in_);

Pid App::left_pid_controller_(Constants::kPidKp, Constants::kPidKd, Constants::kPidKi,
                              Constants::kPidKo, -Constants::kPwmMax, Constants::kPwmMax);
Pid App::right_pid_controller_(Constants::kPidKp, Constants::kPidKd, Constants::kPidKi,
                               Constants::kPidKo, -Constants::kPwmMax, Constants::kPwmMax);

unsigned long App::last_pid_computation_{0};

unsigned long App::last_set_motors_speed_cmd_{0};

bool App::is_imu_connected{false};

MPU6050 App::mpu;

int16_t ax, ay, az;
int16_t gx, gy, gz;
bool blinkState;
#define EARTH_GRAVITY_MS2 9.80665  //m/s2
#define DEG_TO_RAD        0.017453292519943295769236907684886
#define RAD_TO_DEG        57.295779513082320876798154814105



void App::setup() {
  // Required by Arduino libraries to work.
  init();

  serial_stream_.begin(Constants::kBaudrate);

  left_encoder_.begin();
  right_encoder_.begin();

  left_motor_.begin();
  left_motor_.enable(true);
  right_motor_.begin();
  right_motor_.enable(true);

  left_pid_controller_.reset(left_encoder_.read());
  right_pid_controller_.reset(right_encoder_.read());

  // Initialize command shell.
  shell_.set_serial_stream(&serial_stream_);
  shell_.set_default_callback(cmd_unknown_cb);
  shell_.register_command(Commands::kReadAnalogGpio, cmd_read_analog_gpio_cb);
  shell_.register_command(Commands::kReadDigitalGpio, cmd_read_digital_gpio_cb);
  shell_.register_command(Commands::kReadEncoders, cmd_read_encoders_cb);
  shell_.register_command(Commands::kResetEncoders, cmd_reset_encoders_cb);
  shell_.register_command(Commands::kSetMotorsSpeed, cmd_set_motors_speed_cb);
  shell_.register_command(Commands::kSetMotorsPwm, cmd_set_motors_pwm_cb);
  shell_.register_command(Commands::kSetPidsTuningGains, cmd_set_pid_tuning_gains_cb);
  shell_.register_command(Commands::kGetIsImuConnected, cmd_get_is_imu_connected_cb);
  shell_.register_command(Commands::kReadEncodersAndImu, cmd_read_encoders_and_imu_cb);

  // Initialize IMU sensor.

  /*Initialize device and check connection*/ 
  mpu.initialize();

  if(mpu.testConnection() ==  false){
    Serial.println("MPU6050 connection failed");
    is_imu_connected = false;
  }
  else{
    is_imu_connected = true;
  }
  mpu.CalibrateAccel(10);  // Calibration Time: generate offsets and calibrate our MPU6050
  mpu.CalibrateGyro(10);
  /* Use the code below to change accel/gyro offset values. Use MPU6050_Zero to obtain the recommended offsets */ 

  /*Print the defined offsets*/
Serial.print("Accel FS = ");
Serial.println(mpu.getFullScaleAccelRange());

Serial.print("Gyro FS = ");
Serial.println(mpu.getFullScaleGyroRange());

  /*Configure board LED pin for output*/ 
  pinMode(LED_BUILTIN, OUTPUT);
}

void App::loop() {
  // Process command prompt input.
  shell_.process_input();

  // Compute PID output at the configured rate.
  if ((millis() - last_pid_computation_) > Constants::kPidPeriod) {
    last_pid_computation_ = millis();
    adjust_motors_speed();
  }

  // Stop the motors if auto-stop interval has been reached.
  if ((millis() - last_set_motors_speed_cmd_) > Constants::kAutoStopWindow) {
    last_set_motors_speed_cmd_ = millis();
    stop_motors();
  }

  // Required by Arduino libraries to work.
  if (serialEventRun) {
    serialEventRun();
  }
}

void App::adjust_motors_speed() {
  int left_motor_speed = 0;
  int right_motor_speed = 0;
  left_pid_controller_.compute(left_encoder_.read(), left_motor_speed);
  right_pid_controller_.compute(right_encoder_.read(), right_motor_speed);
  if (left_pid_controller_.enabled()) {
    left_motor_.set_speed(left_motor_speed);
  }
  if (right_pid_controller_.enabled()) {
    right_motor_.set_speed(right_motor_speed);
  }
}

void App::stop_motors() {
  left_motor_.set_speed(0);
  right_motor_.set_speed(0);
  left_pid_controller_.disable();
  right_pid_controller_.disable();
}

void App::cmd_unknown_cb(int, char**) { Serial.println("Unknown command."); }

void App::cmd_read_analog_gpio_cb(int argc, char** argv) {
  if (argc < 2) {
    return;
  }

  const int pin = atoi(argv[1]);
  Serial.println(analogRead(pin));
}

void App::cmd_read_digital_gpio_cb(int argc, char** argv) {
  if (argc < 2) {
    return;
  }

  const int pin = atoi(argv[1]);
  Serial.println(digitalRead(pin));
}

void App::cmd_read_encoders_cb(int, char**) {
  Serial.print(left_encoder_.read());
  Serial.print(" ");
  Serial.println(right_encoder_.read());
}

void App::cmd_reset_encoders_cb(int, char**) {
  left_encoder_.reset();
  right_encoder_.reset();
  left_pid_controller_.reset(left_encoder_.read());
  right_pid_controller_.reset(right_encoder_.read());
  Serial.println("OK");
}

void App::cmd_set_motors_speed_cb(int argc, char** argv) {
  if (argc < 3) {
    return;
  }

  const int left_motor_speed = atoi(argv[1]);
  const int right_motor_speed = atoi(argv[2]);

  // Reset the auto stop timer.
  last_set_motors_speed_cmd_ = millis();
  if (left_motor_speed == 0 && right_motor_speed == 0) {
    left_motor_.set_speed(0);
    right_motor_.set_speed(0);
    left_pid_controller_.reset(left_encoder_.read());
    right_pid_controller_.reset(right_encoder_.read());
    left_pid_controller_.disable();
    right_pid_controller_.disable();
  } else {
    left_pid_controller_.enable();
    right_pid_controller_.enable();
  }

  // The target speeds are in ticks per second, so we need to convert them to ticks per
  // Constants::kPidRate.
  left_pid_controller_.set_setpoint(left_motor_speed / Constants::kPidRate);
  right_pid_controller_.set_setpoint(right_motor_speed / Constants::kPidRate);
  Serial.println("OK");
}

void App::cmd_set_motors_pwm_cb(int argc, char** argv) {
  if (argc < 3) {
    return;
  }

  const int left_motor_pwm = atoi(argv[1]);
  const int right_motor_pwm = atoi(argv[2]);

  left_pid_controller_.reset(left_encoder_.read());
  right_pid_controller_.reset(right_encoder_.read());
  // Sneaky way to temporarily disable the PID.
  left_pid_controller_.disable();
  right_pid_controller_.disable();
  left_motor_.set_speed(left_motor_pwm);
  right_motor_.set_speed(right_motor_pwm);
  Serial.println("OK");
}

void App::cmd_set_pid_tuning_gains_cb(int argc, char** argv) {
  // TODO(jballoffet): Refactor to expect command multiple arguments.
  if (argc < 2) {
    return;
  }

  static constexpr int kSizePidArgs{4};
  int i = 0;
  char arg[20];
  char* str;
  int pid_args[kSizePidArgs]{0, 0, 0, 0};

  // Example: "u 30:20:10:50".
  strcpy(arg, argv[1]);
  char* p = arg;
  while ((str = strtok_r(p, ":", &p)) != NULL && i < kSizePidArgs) {
    pid_args[i] = atoi(str);
    i++;
  }
  left_pid_controller_.set_tunings(pid_args[0], pid_args[1], pid_args[2], pid_args[3]);
  right_pid_controller_.set_tunings(pid_args[0], pid_args[1], pid_args[2], pid_args[3]);
  Serial.print("PID Updated: ");
  Serial.print(pid_args[0]);
  Serial.print(" ");
  Serial.print(pid_args[1]);
  Serial.print(" ");
  Serial.print(pid_args[2]);
  Serial.print(" ");
  Serial.println(pid_args[3]);
  Serial.println("OK");
}

void App::cmd_get_is_imu_connected_cb(int, char**) { Serial.println(is_imu_connected); }

void App::cmd_read_encoders_and_imu_cb(int, char**) {
  Serial.print(left_encoder_.read());
  Serial.print(" ");
  Serial.print(right_encoder_.read());
  Serial.print(" ");

  // Retrieve absolute orientation (quaternion). See
  // https://learn.adafruit.com/adafruit-bno055-absolute-orientation-sensor/overview for further
  // information.
  mpu.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);
  

  //Serial.print(((ax/((mpu.getFullScaleAccelRange()+1)*16384.0))/2.0)*EARTH_GRAVITY_MS2); Serial.print(" ");
  //Serial.print(((ay/((mpu.getFullScaleAccelRange()+1)*16384.0))/2.0)*EARTH_GRAVITY_MS2); Serial.print(" ");
  //Serial.print(((az/((mpu.getFullScaleAccelRange()+1)*16384.0))/2.0)*EARTH_GRAVITY_MS2); Serial.print(" ");
  //Serial.print(((gx/((mpu.getFullScaleGyroRange()+1)*131.0))/250.0)*DEG_TO_RAD); Serial.print(" ");
  //Serial.print(((gy/((mpu.getFullScaleGyroRange()+1)*131.0))/250.0)*DEG_TO_RAD); Serial.print(" ");
  //Serial.println(((gz/((mpu.getFullScaleGyroRange()+1)*132.0))/250.0)*DEG_TO_RAD);
  float ax_ms2 = (float)ax / 16384.0 * EARTH_GRAVITY_MS2;
	float ay_ms2 = (float)ay / 16384.0 * EARTH_GRAVITY_MS2;
	float az_ms2 = (float)az / 16384.0 * EARTH_GRAVITY_MS2;
	
	float gx_rads = (float)gx / 131.0 * DEG_TO_RAD;
float gy_rads = (float)gy / 131.0 * DEG_TO_RAD;
float gz_rads = (float)gz / 131.0 * DEG_TO_RAD;

Serial.print(ax_ms2); Serial.print(" ");
Serial.print(ay_ms2); Serial.print(" ");
Serial.print(az_ms2); Serial.print(" ");

Serial.print(gx_rads); Serial.print(" ");
Serial.print(gy_rads); Serial.print(" ");
Serial.println(gz_rads);
  
}

}  // namespace andino
