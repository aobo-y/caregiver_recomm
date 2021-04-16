import smtplib


class sendemail(object):
    """docstring for sendemail"""
    def __init__(self):
        super(sendemail, self).__init__()
        # self.arg = arg
        
    fromaddr = 'M2FED.Monitor@gmail.com'
    #toaddrs = ['M2FED.Monitor@gmail.com','jjj4se@virginia.edu','ay6gv@virginia.edu','ks5qug@virginia.edu']
    toaddrs = ['jjj4se@virginia.edu']
    username = 'M2FED.Monitor@gmail.com'
    password = 'moniM2FED'
    server = smtplib.SMTP('smtp.gmail.com:587')
    server.ehlo()
    server.starttls()
    server.login(username, password)

    def loginGmail(self):
        toaddrs = self.toaddrs
        username = self.username
        password = self.password
        server = smtplib.SMTP('smtp.gmail.com:587')
        server.ehlo()
        server.starttls()
        server.login(username, password)
        return server
     

    # =================Function for email sending  ====(begin)==================================================================================#
    def emailMsg(self, subject, homeID, source, error, message, explanation, contact):
        # print "generating email msg"
        self.server = self.loginGmail()
        msg = "\r\n".join([
            "Subject: " + subject,
            "",
            "HomeID: " + str(homeID) + "\n" +
            "Source: " + source + "\n" +
            "Error: " + error + "\n" +
            "Message: " + message + "\n" +
            "Explanation: " + explanation + "\n" +
            "Contact: " + contact + "\n"
        ])
        return msg
    def send(self, msg):
        self.server.sendmail(self.fromaddr, self.toaddrs, msg)






