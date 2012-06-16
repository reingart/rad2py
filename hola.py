# sample file to test shell & debugger

a = 1
a = 1/0
a = 1/3

def factorial(n):
    """This is the "factorial" function
    >>> factorial(5)
    120
    
    """
    if n is None:
        raise RuntimeError("test exception")
    result = 1
    factor = 2
    while factor <= n:
        result *= factor
        factor += 1
    return result

# funcion principal:

def main(h="CHAU!"):

    a = h
    n = raw_input("nombre?")

    n = n+"ldasf"

    if n:
        print a, n

#asdf = hola
if __name__=="__main__":
    main(j=1)
    
# dafasdfs