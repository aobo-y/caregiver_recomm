from .utils import verify_state

"""
one entry of the config list is composed of:
1. time as minute (10:00 am -> 600) after start
2. time delta in minute that can tolerate before the time in 1
3. time delta in minute that can tolerate after the time in 1
4. function that decides whether the url dict meets the condition, true means correct state
5. next nodes, please note that **NO LOOPS ARE ALLOWED**; for convenience, start node must at index 0
6. choices to return to server; if multiple children, should match with #5
"""

def generate_config(interv=5):
    morning_msg_suids = [19, 20, 23]
    config = []
    for i in range(7):
        # morning message
        b = i * 12

        for j in range(3): 
            config.append(
                [interv * 2 * i, 0, interv, lambda x: verify_state(x, n=j), [b + j + 1], [0, 1]],
            )
        # evening message
        # likert
        time = interv * ( 2 * i + 1)
        config.append([time, interv, interv, lambda x: verify_state(x, n=3), [b + 4], ['1', '2']])
        # daily goal
        config.append([time, interv, interv, lambda x: verify_state(x, n=4), [b + 5, b + 6], ['1', '2']])
        config.append([time, interv, interv, lambda x: verify_state(x, n=5), [b + 7], ['1', '2']])
        config.append([time, interv, interv, lambda x: verify_state(x, n=6), [b + 7], ['1', '2']])
        # ask about recommendation
        config.append([time, interv, interv, lambda x: verify_state(x, n=7), [b + 8, b + 10], ['1', '2']]) # stress_manag1
        config.append([time, interv, interv, lambda x: verify_state(x, n=8), [b + 9, b + 11], ['1', '2']]) # stress_managyes1
        config.append([time, interv, interv, lambda x: verify_state(x, n=9), [b + 11], ['1', '2']]) # stress_managyes2
        config.append([time, interv, interv, lambda x: verify_state(x, n=10), [b + 11], ['1', '2']]) # stress_managno1

        config.append([time, interv, interv, lambda x: verify_state(x, n=11) or x['suid'] == 26, [b + 12], ['1', '2']]) # system_helpful

    base = 85
    time = 12 * interv
    config.append([time, interv, interv, lambda x: verify_state(x, n=12), [base], ['1', '2']])

    config.append([time, interv, interv, lambda x: verify_state(x, n=13), [base + 1, base + 2], ['1', '2']])
    config.append([time, interv, interv, lambda x: verify_state(x, n=14), [base + 2], [0, 1]])

    config.append([time, interv, interv, lambda x: verify_state(x, n=15), [base + 3, base + 4], ['1', '2']])
    config.append([time, interv, interv, lambda x: verify_state(x, n=16), [base + 4], [0, 1]])

    config.append([time, interv, interv, lambda x: verify_state(x, n=17), [base + 5, None], ['1', '2']])
    config.append([time, interv, interv, lambda x: verify_state(x, n=18), [base + 6], ['1', '2']])
    config.append([time, interv, interv, lambda x: verify_state(x, n=19), [], ['1', '2']])

    return config