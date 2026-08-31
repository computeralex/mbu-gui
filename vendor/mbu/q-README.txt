Q -- Debugging and execution framework for bash scripts.
        Attempts to make life easy for the developer.
            Author: Ted Merrill, March 2023

Q FEATURES
===============================================================================
(1) Features are generally optional.
But for full advantage, follow Q programming guidelines.

(2) Parameter passing / value return support :
Makes it simpler to pass values between caller and caller
functions, avoiding some bash horrors,
and adding optional debug capabilities.

(3) Standardized message generation, both user and debug.
Makes it easier to understand the messages.
Debug statements are simple and generally can be left in.

(4) Standardized error handling.

(5) Standarized user interaction.

(6) Interactive debugger

(7) Breakpoint debug method, with or without debugger.

(8) Any program properly written with Q is also a library
That is, you can source it into another script and call its
functions; the script at the top level (that invoked the
other script(s)) decides which function runs first
(or you can drop into the debugger).

(9) You can avoid learning so much about the horrors of bash if
you stick to the subset of bash recommended.
In spite of bash's problems, it is a useful language when
you can solve a problem by tying together a number of
external programs.

Please read the extensive comments at the top of qlib.


Q CAVEATS
===============================================================================
(1) To gain all the advantages, you must do some "mark up" of your
code, and do it consistenly. Not hard, but perhaps not suitable
for a large existing bash program.

(2) If you are worried about efficiency, you would not use bash,
but Q certainly makes it a little worse.

(3) Bash is a quirky, unsafe language. Cannot entirely hide that.


INSTALLATION
===============================================================================
Untar the archive file (probably named q-something.tgz) into a safe place:
    tar -xvf q-something.tgz
Copy the files into a directory where you are building your project.

For updating to a newer version, it is advisable to first compare the
differences with a difference tool such as meld.
Chances are, if you haven't changed anything yourself, you can just copy
the new files to your project directory, replacing the old ones.

The files are:
qlib  -- this is the only important file, has all the code.
qtemplate -- copy this to a new name to start some new code,
    and follow the instructions therein.
qlib-README.txt  -- this file


GETTING STARTED, USAGE INSTRUCTIONS
===============================================================================
Read the extensive comments at the top of "qlib".

In particular, look through "qtemplate", an example script which you can
modify to begin your Q-based programming.


SUPPORT
===============================================================================
This software is unsupported.
I may respond to thoughtful questions or observations emailed to
software AT embuildsw.com


LICENSE
===============================================================================
I, Ted Merrill, am the sole author of the Q software.
You can do whatever you want with this software so long as you don't claim
ownership of what I wrote.


# MBU Release mbu-20251115
