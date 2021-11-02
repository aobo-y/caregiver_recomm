from .rds import RDS

table_name = "ema_storing_data"
deployment_ids = ['6092021','7132021','8022021']

def connect2cloud(table_name):
    '''
        establish a connection to the cloud
    '''
    rds_connection = RDS()
    data = rds_connection.get_all_rows(table_name)
    return data

def get_deployment_ids(data):
    '''
        return a list of all unique deployment ids
    '''
    deployment_ids = []
    for row in data:
        if row[-7] not in deployment_ids:
            deployment_ids.append(row[-7])
    return deployment_ids

def get_updates(deployment_ids, curr_evt_len, curr_choices_len, low_evt=5, high_evt=6, low_choices=22, high_choices=22):
    '''
        for all deployments, return the ctx vector, action, and the reward if not null
        curr_evt_len: current number of feature events in event vector (5 or 6)
        curr_choices_len: number of choices or actions (22)

        To filter out unknown vectors, pick which ones are acceptable
        low_feat: smallest number of features 
        high_feat: highest number of features
        low_choices: smallest number of choices
        high_choices: highest number of choices

    '''
    update_data = {
        'ctx':[],
        'action':[],
        'reward':[]
    }
    #establish a connection
    data = connect2cloud(table_name)
    #check each row
    for row in data:
        try:
            #only use rows of actual deployments
            if row[-7] in deployment_ids:
                #if evnt and stat vector exist
                if (not row[1] == 'null') and (not row[2] == 'null'):
                    ctx, success = format_ctx(row[1],row[2],curr_evt_len, curr_choices_len, low_evt, high_evt, low_choices, high_choices)
                    #Check if action and reward exist and successfully formatted ctx vector
                    if  success and (not row[3] == -1) and (not row[4] ==-1) and (not row[3] == 'null') and (not row[4] == 'null'):
                        #save this data
                        update_data['ctx'].append(ctx)
                        update_data['action'].append(int(row[3]))
                        update_data['reward'].append(int(row[4])) 
        except:
            pass           

    return update_data

def format_ctx(evt_vect, stat_vect, curr_evt_len, curr_choices_len, low_evt, high_evt, low_choices, high_choices):
    ctx = []
    try:
        #Convert string list to list
        evt_vect = evt_vect.strip('[]').split(', ')
        stat_vect = stat_vect.strip('[]').split(', ')
        #Convert string elements to floats
        evt_vect = [float(x) for x in evt_vect]
        stat_vect = [float(x) for x in stat_vect]

        #if acceptable length, fix it by appending zero
        if (len(evt_vect) >= low_evt) and (len(evt_vect) <= high_evt) and (not len(evt_vect) == curr_evt_len):
            assert curr_evt_len > len(evt_vect)

            change = curr_evt_len - len(evt_vect)
            while change > 0:
                evt_vect.append(0)
                change-=1

        
        #if acceptable length, fix it by appending zero
        if (len(stat_vect) >= low_choices) and (len(stat_vect) <= high_choices) and (not len(stat_vect) == curr_choices_len):
            assert curr_choices_len > len(stat_vect)

            change = curr_choices_len - len(stat_vect)
            while change > 0:
                evt_vect.append(0)
                change-=1
        
        #if lengths match acceptable lengths, save them
        if (len(evt_vect) == curr_evt_len) and (len(stat_vect) == curr_choices_len):
            ctx = evt_vect + stat_vect 
            return ctx, True
    except:
        pass

    return ctx, False
    
