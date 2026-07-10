# Host build of the AD5933 numeric-core test (no hardware, no Arduino).
#   make        -> build and run
#   make clean
test_math: test_math.cpp ../src/ad5933_math.h
	c++ -std=c++11 -Wall -I../src test_math.cpp -o test_math
	./test_math

clean:
	rm -f test_math

.PHONY: clean
