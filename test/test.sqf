

//single line comment #definex nothrow

/* multi line comment in oneline #defines nothrow */

/*
	multi line comment

	#definex nothrow
*/

#define GLOBAL_MACRO 1

#define FUNC_MACRO(a,b,c) a + b + c

#define DEF_MACRO

#include "test_incl.h"

#include <infolder\file1.h>

FUNC_MACRO(1,2,3,4)
FUNC_MACRO(1,2)
FUNC_MACRO



#ifdef REF_FILE1

#endif

#ifdef REF_FILE1
	#ifdef INFOLDER_DEFINE
	
	#else

	#endif
#else
	#ifdef INFOLDER_DEFINE
	
	#else
	
	#endif
#endif

#define NUM_TEST123 1

#if NUM_TEST123
	#if NUM_TEST123 >= 1

	#endif
#endif