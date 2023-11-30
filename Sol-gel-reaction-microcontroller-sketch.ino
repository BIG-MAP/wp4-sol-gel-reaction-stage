#include <SPI.h>
#include <Ethernet.h>
#include <EthernetClient.h>
#include <SoftwareSerial.h>
#include <Wire.h>

// the media access control (ethernet hardware) address for the shield:
byte mac[] = { 0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED };  
//the IP address for the shield:
byte ip[] = { 138, 253, 143, 253 };   
byte gateway[] = { 138, 253, 143, 1};
byte subnet[] = { 255, 255, 255, 0};

EthernetServer server(80);
// String trueIP1 = "138.253.19.150";
// String trueIP2 = "138.253.143.251";

String readString;

String DAVal;
String RAVal;
String DatVal;
int checksum = 0;
int data = -1;

// String testIP;
// String testIP1;
// String testIP2;
// String testIP3;
// String testIP4;

SoftwareSerial mySerial(6, 7); // RX, TX
int writeValue;

void setup()
{
  Wire.begin(); // For communications with thermocouple Arduino
  Serial.begin(9600);
  while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
  }

  mySerial.begin(19200);
  // mySerial.print("Test1");
  // delay(10);

  Ethernet.begin(mac, ip, gateway, subnet);
  server.begin();
  
    // mySerial.isListening();


  Serial.println("Successfully Configured IP Address");
  
  Serial.print("Server is at ");
  Serial.println(Ethernet.localIP());
  Serial.println("Arduino Control Test Interface 4.0");

}

void loop () {
  // listen for incoming clients, checks that IP address matches the approved values (check client IP if script breaks)
    
 

    EthernetClient client = server.available();
    // testIP1 = client.remoteIP()[0];
    // testIP2 = client.remoteIP()[1];
    // testIP3 = client.remoteIP()[2];
    // testIP4 = client.remoteIP()[3];

    // testIP = testIP1+"."+testIP2+"."+testIP3+"."+testIP4;
    

    if (client)
      {
        Serial.println("New client, IP Address Accepted:");

        // mySerial.print("Test2");
        // delay(10);

        Serial.println(client.remoteIP());
        
                while (client.connected())
          {
            if (client.available())
              {
                char c = client.read();
                //read char by char HTTP request
                if (readString.length() < 100)
                  {
                    //store characters to string
                    readString += c;
                    //Serial.print(c);
                    Serial.write(c);
                    // if you've gotten to the end of the line (received a newline
                    // character) and the line is blank, the http request has ended,
                    // so you can send a reply
                    //if HTTP request has ended
                    if (c == '\n') {
                        Serial.println(readString); //print to serial monitor for debuging

            // Needed to Display Site:
                        client.println("HTTP/1.1 200 OK"); //send new page
                        client.println("Content-Type: text/html");
                        client.println();
                        client.println("<HTML>");
                        //client.println("<HEAD>");

            // what is being Displayed :    
                        // client.println("<TITLE>Arduino Test</TITLE>");
                        // client.println("<center>");
                        // client.println("</HEAD>");
                        client.println("<BODY>");
                        // client.println("<H1>Arduino Test Interface</H1>");
                        // client.println("<hr />");
                        // client.println("<center>");
                        // client.println("<br />");
                        // client.println("<br />");
                        // client.println("<H3>Checksum from server = "+String(checksum)+"</H3>");
                        // client.println("<H3>Data from server = "+String(data)+"</H3>");

                        client.println("<br />");
                        client.println("<form method = \"GET\" action = \"/\" id = \"M1\">");
                        // client.println("<p>Enter Dev. Adr., RAM Adr., DATA Write:</p>");
                        //client.println("<label for=\"dv\">Device Adr. byte (0 - 255):</label>");
                        client.println("<input type=\"number\" id=\"dv\" name=\"dv\" min=\"0\" max=\"255\"><br>");
                        //client.println("<label for=\"rv\">RAM byte (32 - 86 w, 87 - 214 r):</label>");
                        client.println("<input type=\"number\" id=\"rv\" name=\"rv\" min=\"32\" max=\"214\"><br>");
                        //client.println("<label for=\"dtv\">DATA byte (0 - 255), blank for r:</label>");
                        client.println("<input type=\"number\" id=\"dtv\" name=\"dtv\" min=\"0\" max=\"255\"><br><br>");
                        client.println("<input type=\"submit\" value=\"Send\">");
                        client.println("</form><br><br>");


                        client.println("</BODY>");
                        client.println("</HTML>");
                        delay(1);

                        data = -1; // interface will display data from last refresh, this sets it back in case no new values


                        DAVal = readString.substring(readString.indexOf("?dv="),readString.indexOf("&rv"));
                        DAVal.remove(0,4); // removes the id from the string, leaving only the value
                        RAVal = readString.substring(readString.indexOf("&rv="),readString.indexOf("&dtv"));
                        RAVal.remove(0,4);
                        DatVal = readString.substring(readString.indexOf("&dtv="),readString.indexOf(" HTTP/1.1"));
                        DatVal.remove(0,5);

                        Serial.println("Ints sent: ");
                        Serial.println(DAVal);
                        
                        Serial.println(RAVal);
                        

                        mySerial.write(byte((DAVal.toInt()))); // Turns the string into an integer (which will be displayed as ASCII in PuTTY)
                        
                        mySerial.write(byte((RAVal.toInt()))); // Turns the string into an integer (which will be displayed as ASCII in PuTTY)

                        if (DAVal.toInt() == 40){ // For communications to be sent to the RS9000 orbit shaker

                        if (RAVal.toInt() < 87){
                        Serial.println(DatVal);
                        mySerial.write(byte((DatVal.toInt()))); // Turns the string into an integer (which will be displayed as ASCII in PuTTY)
                        }

                        Serial.println("Ints received: ");

                        if (RAVal.toInt() > 86){
                        data = mySerial.read();
                        Serial.println("Data: ");
                        Serial.println(data);
                        }
                        Serial.println("Checksum: ");
                        checksum = mySerial.read();
                        Serial.println(checksum);

                        }

                        if (DAVal.toInt() == 8){ // For communications to be sent to the Arduino MKR thermocouple board

                        Serial.println("Communicating with MKR board");
                        
                        Wire.requestFrom(8,2);  // This requests 2 bytes from the device with address '8' (set in sketch for thermocouple Arduino MKR)
                        while (Wire.available()){
 
                          if (RAVal.toInt() == 128){  // Request for the temp low byte
                            Serial.print(".");
                            Wire.read();
                            data = Wire.read();
                            Serial.println(data);
                            }
                          if (RAVal.toInt() == 129){  // Request for the temp high byte
                            Serial.println("Thermocouple Temperature: ");
                            data = Wire.read();
                            Wire.read();
                            Serial.println(data);
                            }  
                          }
                        }

                        if (DAVal.toInt() == 4){

                        }
                        

                        // client.println("<p>Checksum, DATA Read:</p>");
                        client.println("<form method = \"GET\" action = \"/\" id = \"M2\">");
                        //client.println("<label for=\"cs\">Prev. Checksum:</label>");
                        client.println("<input type=\"number\" id=\"cs\" name=\"cs\" value="+String(checksum)+"><br><br>");
                        //client.println("<label for=\"dr\">Prev. data r:</label>");
                        client.println("<input type=\"number\" id=\"dr\" name=\"dr\" value="+String(data)+"><br><br>");
                        client.println("<input type=\"submit\" value=\"Verify\">");
                        client.println("</form><br><br>");


                        client.stop();


                        //clearing string for next read
                        readString = "";
                        // give the web browser time to receive the data
                        delay(1);
                        // close the connection:
                        client.stop();
                        

                        Serial.println("client disonnected");
                     
          }
                 
        }
             
      }
         
    }
     
  }
}
