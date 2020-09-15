import sendemail as se

home_id = "123" # get home id from deployment.db



# ================= for email sending  ====(begin)==================================================================================#
subject = "CRITICAL: Home [" + home_id + "] Base station" # CRITICAL, ALERT, NOTIFICATION

source = "Laptop process" 
error = "[ProcessCheckThread]"
message = "XXX Process stops running" # describe the error 
explanation = "The audio program is not working/processing the data. UVA needs to log on the laptop and identify the error. " # copy error message & potential solution if there is one
contact = "UVa Team" 

semail = se.sendemail()

msg = semail.emailMsg(subject, home_id, source, error, message, explanation, contact);
semail.send(msg)
# print msg

# self.server.sendmail(self.fromaddr, self.toaddrs, msg)
# ================= for email sending  ====(end)==================================================================================#

