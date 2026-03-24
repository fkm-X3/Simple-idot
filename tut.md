# This is a basic tut for simple idot

## Comments
```
/// Important header comment ///

// Single line comments

/*
Multi line comment
*/

~ documentation comments ~
```

## Variables
"let" assigns variables

The first time X (our variable) is mentioned assigns X the value "5" like putting it into a box for later use.
The second time X is mentioned it is reassigned the value "10" (note: this value can be a number or text)

A variable without a "let" is a reassignment of the value

"const" makes values unable to be changed or reasigned

## Printing variables
when printing out variables there are 2 things to understand
```
x = "hello world"

print(x)
print("the variable x is", {x})
```
you can print a variable directly with the print command (print(x)), or you can print out some text first then the variable (print("test text", {x}))

## Script reference
Simple-idot can reference other simple-idot scripts or other scripts

Referencing other .idot scripts
```
bring "example.idot" as test
```
Referencing external scripts
```
bring(py) "example.py" as py_example
bring(js) "example.js" as js_example
```

# Getting input
Collecting te users input is as simple as
```
input_get()
```
then save it as a variable 
```
let x = input_get()
```
