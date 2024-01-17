/*
  MKR THERM Shield - Read Sensors

  This example reads the temperatures measured by the thermocouple
  connected to the MKR THERM shield and prints them to the Serial Monitor
  once a second.
  
  The circuit:
  - Arduino MKR board
  - Arduino MKR THERM Shield attached
  - A K Type thermocouple temperature sensor connected to the shield
 
  This example code is in the public domain.

// Wire Peripheral Sender
// by Nicholas Zambetti <http://www.zambetti.com>
// Demonstrates use of the Wire library
// Sends data as an I2C/TWI peripheral device
// Refer to the "Wire Master Reader" example for use with this
// Created 29 March 2006
// This example code is in the public domain.


*/

#include <Arduino_MKRTHERM.h>
#include <Wire.h>

int sendByteHigh;
int sendByteLow;
float TempReading;

void setup() {
 Wire.begin(8); // Assigns the address '8' to the thermocouple Arduino
 Wire.onRequest(requestTemp); // When a request is made by another microcontroller, the function 'requestTemp' will be executed
 Serial.begin(9600);
  // while (!Serial) {
  //   ; // wait for serial port to connect. Needed for native USB port only
  // } 

  if (!THERM.begin()) { // Make sure something like this is included, otherwise the temperature measurements won't happen
    Serial.println("Failed to initialize MKR THERM shield!");
    while (1);
 
  }

  Serial.println("MKR awaiting requests");
  
}

void loop() {

  //Serial.println();

  delay(1); // Ensures there is a gap between data sending, so data does not overflow
}

void requestTemp() {
  TempReading = THERM.readTemperature();
  Serial.println("Thermocouple Temp Reading: ");
  Serial.println(TempReading);
  sendByteHigh = byte(int(TempReading));  // The temp reading is broken into individual bytes either side of the decimal point
  sendByteLow = byte(int(((TempReading-float(sendByteHigh))*100)));
  Serial.println("High byte to send: ");
  Serial.println(sendByteHigh);
  Wire.write(sendByteHigh); // The high and low bytes are sent seperately
  Serial.println("Low byte to send: ");
  Serial.println(sendByteLow);
  Wire.write(sendByteLow);
}
