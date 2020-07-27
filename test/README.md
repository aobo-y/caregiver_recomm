# Recommender Testing
## Usage
### If you want to change business logic
1. Edit `msg_config.json`, put all messages that will appear in the questions that will be sent to user. The format for each entry is:
   ```js
   {
       'prefix_1' : {
           'postfix_1' : [number_from, number_to],
           'postfix_2' : [number_from, number_to],
           ...
       },
       'prefix_2' : {
           'postfix_1' : [number_from, number_to],
           'postfix_2' : [number_from, number_to],
           ...
       },
       ...
   }
   ```
   The message name can contain no number, a message like this should have an empty array to correspond to this.
   The numbers are inclusive.
2. Edit `generate_config` in [config.py](config.py), return a state config array in which each entry is an array with:
   1. time as seconds after start
   2. time delta in seconds that can tolerate before the time in 1
   3. time delta in seconds that can tolerate after the time in 1
   4. function that decides whether the url dict meets the condition, true means correct state
   5. next nodes, please note that **NO LOOPS ARE ALLOWED**;  start node must at index 0, we don't want to loop the config array just looking for the start node.
   6. choices to return to server; if multiple children, should match with #5
    
    For the sake of convenience, we provide a `ConfigMaker` class that you can use. Please notice that if you want to add no-response states (states that the automata will go to if the answer to the recommender is `None`) with the method `make_no_response_states`, you have to put the default next state to the first in "next nodes". See the documentation for `ConfigMaker` in [config.py](config.py) for reference.

### If you want to change test configuration
The tester has two parameters that can be configured:
1. `day_repeat`, the number of "days" (i.e. one iteration that goes through all the scheduled events) before the weekly survey.
2. `interval`, the time interval between two events.
You can change these two parameters in [run_tests.py](run_test.py)

### To run the tests
```shell
sh init_db.sh
export FLASK_APP=run_test.py
flask run
```