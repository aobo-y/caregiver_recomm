def test():
    return 1, 2, 3

def another(a=1, b=2, c=3):
    print(a)
    print(b)
    print(c)

param = {'a': 4, 'b':5}

another(param)