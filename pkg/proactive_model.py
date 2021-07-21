import pandas as pd
from matplotlib import pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import PolynomialFeatures
from sklearn.linear_model import LogisticRegression
from sklearn.linear_model import LinearRegression
from sklearn import metrics
import seaborn as sn
import matplotlib.pyplot as plt
import numpy as np
import pymysql
import random
from .log import log
from datetime import datetime, timedelta

def get_conn():
    return pymysql.connect(host='localhost', user='root', password='', db='ema')

def read_data():
    '''
    Read in data from ema tables

    '''
    df = None
    success = False
    try:
        db = get_conn()
        cursor = db.cursor()
        #read entire reward data ema table
        query = "SELECT * FROM reward_data"
        data = cursor.execute(query)
        cursor_fetch = cursor.fetchall()
        df = pd.DataFrame(list(cursor_fetch), columns=['speakerID','empathid','TimeSent','suid','TimeReceived','Response','Question','QuestionType','QuestionName','Reactive','SentTimes','ConnectionError','Uploaded'])

        success = True   
    except Exception as err:
        log('read_data() failed to read reward_data table in proactive_model.py', str(err))
        db.rollback()    
    finally:
        # ensure db closed, exception is raised to upper layer to handle
        db.close()
        #return the if successful and dataframe
        return success, df

def read_startDate():
    '''
        startDate: what date to start reading data from table. Start of deployment date
    '''

    startDate = None
    success = False
    try:
        db = get_conn()
        cursor = db.cursor()

        query = "SELECT FirstStartDate FROM recomm_saved_memory"
        data = cursor.execute(query)
        mystoredData = cursor.fetchone()  #fetches first row of the record

        #save information from table
        startDate = mystoredData[0]
        #change to datetime
        startDate = datetime.strptime(startDate, '%Y-%m-%d %H:%M:%S')

        success = True
    except Exception as err:
        log('read_startDate() failed to read recomm_saved_memory table in proactive_model.py', str(err))
        db.rollback()    
    finally:
        # ensure db closed, exception is raised to upper layer to handle
        db.close()

        #return if successful and startdate
        return success, startDate

def generate_proactive_models():
    '''
        Uses the baseline time and response to train a polynomial regression model
        return a regression model or None if unsuccessful

        This is run once after the baseline period in proactive_recomm()

        and every evening in scheduled_evts()
    '''

    saved_model = None

    try:
        #read the reward_data table
        data_success, df = read_data()
        time_success, startdate = read_startDate()

        if (data_success == True) and (time_success == True):

            #change time to datetime
            df['TimeSent'] = pd.to_datetime(df['TimeSent'], format='%Y-%m-%d %H:%M:%S')
            #use rows only after deployment startdate
            df = df.loc[df['TimeSent'] >= startdate] 

            #get the time and response of the baseline check in 
            baseline_actions_timesent = df.loc[df['QuestionName']=='baseline:recomm:likertconfirm:1','TimeSent'].tolist()
            baseline_actions_reponse = df.loc[df['QuestionName']=='baseline:recomm:likertconfirm:1','Response'].tolist()

            #when normal period start using time of if the recommendation was helpful
            post_recomm_time = df.loc[df['QuestionName']=='daytime:postrecomm:helpfulyes:1','TimeSent'].tolist()
            post_recomm_reward = df.loc[df['QuestionName']=='daytime:postrecomm:helpfulyes:1','Response'].tolist()
            #subtract 30 minutes from post_recomm_time because a recommendation takes at least 30 minutes pause
            for time_idex in range(0,len(post_recomm_time)):
                post_recomm_time[time_idex] = post_recomm_time[time_idex] - timedelta(minutes=30)

            #join the lists
            timessent_lst = baseline_actions_timesent + post_recomm_time
            angry_helpful_lst = baseline_actions_reponse + post_recomm_reward

            fnl_bline_act_timesent_lst = []
            fnl_bline_act_reponse_lst = []
            for i in range(0,len(timessent_lst)):
                #change reponses to in not angry: 0.0 to angry: 10.0, -1.0
                angry_helpful_lst[i] = int(float(angry_helpful_lst[i]))

                #if no response remove
                if angry_helpful_lst[i] != -1.0:
                    fnl_bline_act_reponse_lst.append(angry_helpful_lst[i])
                    #get the hour sent
                    fnl_bline_act_timesent_lst.append(timessent_lst[i].hour)

            #check enough data
            if (len(fnl_bline_act_reponse_lst) < 30) or (len(fnl_bline_act_timesent_lst) < 30):
                return saved_model
       
            #put in dictionary
            data_dict = {'hour':fnl_bline_act_timesent_lst,
                                'angry':fnl_bline_act_reponse_lst}
            #put dictionary in pandas dataframe
            df_for_model = pd.DataFrame(data_dict,columns= ['hour','angry'])

            #set independent and dependent variables
            X = df_for_model[['hour']]
            Y = df_for_model['angry']

            #test train split
            X_train,X_test,Y_train,Y_test = train_test_split(X,Y,test_size=0.1,random_state=0)

            #use polynomial regression
            poly_reg = PolynomialFeatures(degree=4)
            #transform independent variable to polynomial
            X_poly = poly_reg.fit_transform(X_train)
            # initialize linear regression
            lin_reg = LinearRegression()
            #input the transformed independent variable and train model
            saved_model = lin_reg.fit(X_poly,Y_train)
        else:
            log('generate_proactive_models() failed, no data')
    except Exception as err:
        log('Error in generate_proactive_models()',str(err))
    finally:
        #either the model or None
        return saved_model

    
def get_proactive_prediction(hour,model):
    '''
        Pass in a time and return 0: dont send recomm, 1: send recomm
        Pass in the model 

        Return if successful and if send proactive recomm or not 0: dont sent 1:send
        (True,1) or (True,0)
    '''
   
    send_proact_recomm = None
    success = False
    try:
        #check if we have a model 
        if model == None:
            return success, send_proact_recomm

        #initilaize polynomial regression for transforming hour
        poly_reg = PolynomialFeatures(degree=4)

        log('Proactive model predicting...')
        #pass hour to model
        Y_pred = model.predict(poly_reg.fit_transform([[hour]]))

        #if angry level >= 4 then yes send
        Y_pred = float(Y_pred[0])
        if Y_pred >=4:
            send_proact_recomm = 1
        else:
            send_proact_recomm = 0

        log('Proactive model predicts:',send_proact_recomm) 
        
        success = True
    except Exception as err:
        log('Error in get_proactive_prediction', str(err))
    finally:
        #if we get to the end return False None or True 0/1
        return success,send_proact_recomm

#my_model = generate_proactive_models()
#print(my_model)
#print(get_proactive_prediction(17,my_model))

#plot
# mymodel = np.poly1d(np.polyfit(fnl_bline_act_timesent_lst, fnl_bline_act_reponse_lst, 4))
# myline = np.linspace(0, 23, 100)
# plt.scatter(fnl_bline_act_timesent_lst,fnl_bline_act_reponse_lst)
# plt.plot(myline,mymodel(myline))
# plt.show()

# fnl_bline_act_reponse_lst = [1, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,1, 1, 1, 0, 0, 0, 0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
# fnl_bline_act_timesent_lst = [2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7]
    
#change to categorical
# df_for_model['hour'] = df_for_model.hour.astype('category')
# df_for_model['angry'] = df_for_model.angry.astype('category')

#predict
#Y_pred = lin_reg.predict(poly_reg.fit_transform(X_test))
#since polynomial regression use 
#mean_ab_err = metrics.mean_absolute_error(Y_pred,Y_test) #.14
#print(mean_ab_err)
# print(X_test)
# print(Y_pred)
# print(type(Y_pred))
# print(Y_pred[0],type(int(Y_pred[0])))

# #use logistic regression
# logistic_regression = LinearRegression() #LogisticRegression()
# #train the model
# logistic_regression.fit(X_train,y_train)
# y_pred=logistic_regression.predict(np.array([3]).reshape(1,-1))
# #y_pred=logistic_regression.predict(X_test)
#acc = metrics.accuracy_score(y_test,y_pred)
#print(acc)