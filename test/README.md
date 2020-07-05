# Recommender Testing
## Usage
### If you want to change business logic
1. Edit `msg_config.json`, put all messages that will appear in the questions that will be sent to user. The format for each entry is:
   ```
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
   The numbers are inclusive.
2. Edit `generate_config` in `config.py`, return a state config array in which each entry is an array with:
   1. time as minute (10hr -> 600) after start
   2. time delta in minute that can tolerate before the time in 1
   3. time delta in minute that can tolerate after the time in 1
   4. function that decides whether the url dict meets the condition, true means correct state
   5. next nodes, please note that **NO LOOPS ARE ALLOWED**;  start node must at index 0, we don't want to loop the config array just looking for the start node.
   6. choices to return to server; if multiple children, should match with #5
    
    For the sake of convenience, we provide a `ConfigMaker` class that you can use. Please notice that if you want to add no-response states (states that the automata will go to if the answer to the recommender is `None`) with the method `make_no_response_states`, you have to put the default next state to the first in "next nodes".
### To run the tests