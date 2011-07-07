# sample file to test shell & debugger

def factorial(n):
    """This is the "factorial" function
    >>> factorial(5)
    120
    >>> factorial(None)
    0
    
    """
    if n is None:
        raise RuntimeError("test exception")
    result = 1
    factor = 2
    while factor <= n:
        result *= factor
        factor += 1
    return result

def main(h="hola"):
    a = h
    n = raw_input("nombre?")

    n = n+"ldasf"

    if n:
        print a, n
        

#asdf = hola
if __name__=="__main__":
    main(h=1)
