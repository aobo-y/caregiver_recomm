# Testing
## Testing the recommender
### Current tests
There are three tests currently available: regular test, cooldown test, start-time test.

* Regular test: dispatch the events once every hour, see whether the recommender will respond with expected action.
* Cooldown test: dispatch the event within the cooldown period.
* Start-time test: dispatch the event before the starting time, and then after the starting test.

Apart from these, there is also a test-suite `statistics`, which will collect the number of time that each candidate action is sent to the care-giver.

Through the tests, we can ensure that:

* The recommender will give the followup question after send the action to the care-giver for the appropriate amount of time.
* After the followup question, the recommender will send the correct question according to whether the care-giver implements the action.
* The recommender will follow the desired behavior: it will not send action within the cool-down period, before the start-time, or after the end-time.
* The recommender will receive correct reward.

### Adding more tests

To add more tests to the recommender, in [test_recommender.py](test_recommender.py), add or edit a entry in `test_suites`, in the form of:
```python
'{name_of_this_test_suite}': {
    'config': function_that_generates_config_array,
    'time_between_routes': time_sleep_before_new_route_starts,
    'recommender_test_config': {
        'scale': scale,
        'fake_start': True,
        'start_hr': 11
    }
}
```
Note: 
* `time_between_routes` is usually set to `sleep_time` minus the approximate amount of time for each route to complete.
* Scale the time so that the test will complete in a reasonable amount of time.
* Fake start is the time that you want to start the recommender. For example, if you want the test to start at 11 am, set `fake_start` to `True` and set `start_hr` to 11.

### Start testing
In this directory, run
```shell
sh init_db.sh
export FLASK_APP=test_recommender.py
flask run
```

## Testing the scheduled events
### Current tests
The current test will generate all the possible paths to respond to the scheduled events, and verify that the behavior of the scheduled events is desired.

### Change logic

If you changed the scheduled events, **please edit the test by yourself**.

1. Edit the `make_config` function in [test_schedule_event.py](test_schedule_event.py). Use `ConfigMaker` to aid this process. Please see the documentation of `ConfigMaker` in [config.py](config.py) for reference.

2. The format for the messages is:
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

### If you want to change test configuration
The tester has two parameters that can be configured:
1. `day_repeat`, the number of "days" (i.e. one iteration that goes through all the scheduled events) before the weekly survey.
2. `interval`, the time interval between two events.
You can change these two parameters in [run_tests.py](run_test.py)

### To run the tests
```shell
sh init_db.sh
export FLASK_APP=test_schedule_event.py
flask run
```