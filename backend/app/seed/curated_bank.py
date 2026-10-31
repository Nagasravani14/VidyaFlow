"""
Curated, hand-verified question bank used as the fallback when the AI provider
is unavailable (source="curated_fallback" in the API, labelled in the UI).

Rules for this file
-------------------
* No placeholders, no "Option A/B" filler, no generic stems.
* Every computed answer has a ``verify`` list that tests/test_quiz_models.py
  re-computes with sympy, independently of the typed key.
* MCQ-style options are authored as correct text + (distractor, misconception)
  pairs. The seeder assigns letters with a deterministic shuffle so the correct
  key is not always "A". ``shuffle=False`` keeps a fixed order (used for
  assertion/reason, whose four options are a standard fixed set).
* Numbers use ASCII "-" (the grader normalises unicode minus signs as well).

verify entry forms
------------------
("eval",  "python/sympy expr", "expected")       expr must equal expected
("solve", "lhs = rhs", "x", "expected")         solving for x gives expected ("none" = no solution)
("equiv", "expr1", "expr2", True|False)         expr1 - expr2 simplifies to 0 (or not)
"""

CONCEPTS = [
    {
        "key": "int",
        "class_num": 6,
        "subject": "Mathematics",
        "name": "Integer Operations",
        "chapter": "Integers",
        "description": "Adding, subtracting, multiplying and dividing positive and negative integers, "
        "including number-line reasoning and sign rules.",
    },
    {
        "key": "alg",
        "class_num": 7,
        "subject": "Mathematics",
        "name": "Algebraic Expressions",
        "chapter": "Algebraic Expressions",
        "description": "Terms, coefficients, like terms, simplifying, adding/subtracting expressions and "
        "evaluating expressions by substitution.",
    },
    {
        "key": "lin",
        "class_num": 8,
        "subject": "Mathematics",
        "name": "Linear Equations",
        "chapter": "Linear Equations in One Variable",
        "description": "Forming and solving linear equations in one variable, checking solutions and "
        "reasoning about methods.",
    },
]

# (concept_key, prerequisite_key): the first requires the second.
PREREQUISITES = [("alg", "int"), ("lin", "alg")]

_AR_OPTIONS = [
    ("Both A and R are true, and R is the correct explanation of A.", None),
    ("Both A and R are true, but R is not the correct explanation of A.", "Judged the reason as unrelated even though it explains the assertion"),
    ("A is true, but R is false.", "Rejected a true reason"),
    ("A is false, but R is true.", "Accepted a false assertion"),
]


def _ar(correct_idx):
    """Assertion-reasoning options: fixed standard set, correct one chosen by index."""
    return {"fixed_options": _AR_OPTIONS, "correct_index": correct_idx}


BANK = [
    # =====================================================================
    # INTEGER OPERATIONS (Class 6)
    # =====================================================================
    # ---- L1 Remember
    {
        "concept": "int", "level": 1, "type": "mcq",
        "objective": "Add two negative integers.",
        "stem": "What is the value of (-5) + (-3)?",
        "correct": "-8",
        "distractors": [
            ("2", "Subtracted the magnitudes instead of adding them"),
            ("8", "Ignored the negative signs"),
            ("-2", "Subtracted 3 from -5 using the wrong direction"),
        ],
        "hint": "Adding a negative number moves you further left on the number line.",
        "explanation": "Both numbers are negative, so add their sizes (5 + 3 = 8) and keep the negative sign: (-5) + (-3) = -8.",
        "verify": [("eval", "(-5)+(-3)", "-8")],
    },
    {
        "concept": "int", "level": 1, "type": "true_false",
        "objective": "Recall the additive inverse.",
        "stem": "True or false: the additive inverse of -7 is 7.",
        "answer": True,
        "hint": "The additive inverse is the number you add to get 0.",
        "explanation": "(-7) + 7 = 0, so 7 is the additive inverse of -7.",
        "verify": [("eval", "(-7)+7", "0")],
    },
    {
        "concept": "int", "level": 1, "type": "fill_blank",
        "objective": "Recall the sum of an integer and its additive inverse.",
        "stem": "The sum of any integer and its additive inverse is ____.",
        "accepted": ["0", "zero"],
        "hint": "Think of 4 + (-4).",
        "explanation": "An integer and its additive inverse cancel each other, so their sum is always 0.",
        "conceptual": True,
    },
    # ---- L2 Understand
    {
        "concept": "int", "level": 2, "type": "mcq",
        "objective": "Explain subtraction of a negative integer.",
        "stem": "Which statement correctly explains why (-4) - (-6) = 2?",
        "correct": "Subtracting -6 is the same as adding 6, so -4 + 6 = 2.",
        "distractors": [
            ("Two negatives make a negative, so the answer is -10.", "Applied 'two negatives' to addition of magnitudes"),
            ("Subtracting always makes a number smaller, so the answer must be below -4.", "Believed subtraction always decreases"),
            ("The signs cancel, so it is 4 - 6 = -2.", "Dropped the signs and subtracted in the wrong order"),
        ],
        "hint": "Subtracting a negative number is the opposite of subtracting a positive one.",
        "explanation": "Subtracting a negative is the same as adding its opposite: (-4) - (-6) = (-4) + 6 = 2.",
        "verify": [("eval", "(-4)-(-6)", "2"), ("eval", "(-4)+6", "2")],
    },
    {
        "concept": "int", "level": 2, "type": "numerical",
        "objective": "Use a number line to add a positive integer to a negative integer.",
        "stem": "On a number line you start at -3 and move 5 units to the right. Which integer do you land on?",
        "answer": "2", "tolerance": 0,
        "hint": "Moving right means adding. Count 3 steps to reach 0, then the rest.",
        "explanation": "Moving 5 units right from -3 is (-3) + 5 = 2.",
        "verify": [("eval", "-3+5", "2")],
    },
    {
        "concept": "int", "level": 2, "type": "true_false",
        "objective": "Understand the sign rule for division.",
        "stem": "True or false: (-6) / 3 has the same value as 6 / (-3).",
        "answer": True,
        "hint": "Work out the sign of each quotient first, then the size.",
        "explanation": "A negative divided by a positive is negative, and a positive divided by a negative is negative. Both equal -2.",
        "verify": [("eval", "(-6)/3", "-2"), ("eval", "6/(-3)", "-2")],
    },
    # ---- L3 Apply
    {
        "concept": "int", "level": 3, "type": "numerical",
        "objective": "Apply integer addition to a temperature change.",
        "stem": "At night the temperature was -4 degrees Celsius. By noon it had risen by 11 degrees. What was the temperature at noon, in degrees Celsius?",
        "answer": "7", "tolerance": 0,
        "hint": "A rise in temperature is added to the starting value.",
        "explanation": "Noon temperature = -4 + 11 = 7 degrees Celsius.",
        "verify": [("eval", "-4+11", "7")],
    },
    {
        "concept": "int", "level": 3, "type": "mcq",
        "objective": "Apply integer addition and subtraction to a depth problem.",
        "stem": "A diver is 12 m below sea level (-12). She rises 5 m and then dives 9 m. Where is she now, relative to sea level?",
        "correct": "-16 m",
        "distractors": [
            ("-26 m", "Treated the 5 m rise as another descent"),
            ("-2 m", "Ignored that the starting point was below sea level"),
            ("2 m", "Treated the 9 m dive as an ascent"),
        ],
        "hint": "Rising adds to the depth value, diving subtracts. Do the moves in order.",
        "explanation": "-12 + 5 = -7, then -7 - 9 = -16, so she is 16 m below sea level.",
        "verify": [("eval", "-12+5-9", "-16")],
    },
    {
        "concept": "int", "level": 3, "type": "fill_blank",
        "objective": "Apply the sign rule for multiplication and then add.",
        "stem": "(-8) x (-3) + (-10) = ____",
        "accepted": ["14"],
        "hint": "Multiply first: two negatives give a positive.",
        "explanation": "(-8) x (-3) = 24, and 24 + (-10) = 14.",
        "verify": [("eval", "(-8)*(-3)+(-10)", "14")],
    },
    # ---- L4 Analyze
    {
        "concept": "int", "level": 4, "type": "mcq",
        "objective": "Compare products by analysing the number of negative factors.",
        "stem": "Let P = (-2) x (-3) x (-4), Q = (-2) x 3 x 4 and R = 2 x 3 x 4. Which statement is true?",
        "correct": "P = Q, and R is the opposite of both.",
        "distractors": [
            ("P = R, because the numbers are the same size.", "Ignored the effect of negative factors on the sign"),
            ("Q = R, because only one factor is negative.", "Thought one negative factor does not change the sign"),
            ("P, Q and R are all equal.", "Compared only the sizes of the numbers"),
        ],
        "hint": "Count the negative factors in each product: odd gives negative, even gives positive.",
        "explanation": "P has three negative factors so P = -24. Q has one negative factor so Q = -24. R has none so R = 24, the opposite of -24.",
        "verify": [("eval", "(-2)*(-3)*(-4)", "-24"), ("eval", "(-2)*3*4", "-24"), ("eval", "2*3*4", "24")],
    },
    {
        "concept": "int", "level": 4, "type": "multi_select",
        "objective": "Identify all expressions equal to a target integer.",
        "stem": "Select ALL the expressions that equal -12.",
        "correct_set": ["(-3) x 4", "6 - 18"],
        "distractors": [
            ("(-24) / (-2)", "Forgot that a negative divided by a negative is positive"),
            ("(-2) x (-6)", "Forgot that a negative times a negative is positive"),
        ],
        "hint": "Evaluate each expression separately and check its sign.",
        "explanation": "(-3) x 4 = -12 and 6 - 18 = -12. But (-24) / (-2) = 12 and (-2) x (-6) = 12.",
        "verify": [
            ("eval", "(-3)*4", "-12"), ("eval", "6-18", "-12"),
            ("eval", "(-24)/(-2)", "12"), ("eval", "(-2)*(-6)", "12"),
        ],
    },
    {
        "concept": "int", "level": 4, "type": "mcq",
        "objective": "Find a counterexample to a claim about subtraction.",
        "stem": "Which pair (a, b) shows that the rule 'a - b = b - a' is NOT always true?",
        "correct": "a = 5, b = 2",
        "distractors": [
            ("a = 3, b = 3", "Picked a pair where both sides happen to be equal"),
            ("a = 0, b = 0", "Picked a pair where both sides happen to be equal"),
            ("a = -4, b = -4", "Picked a pair where both sides happen to be equal"),
        ],
        "hint": "A counterexample must make the two sides different.",
        "explanation": "For a = 5, b = 2: a - b = 3 but b - a = -3, so the sides differ. The other pairs give equal sides, so they do not disprove the rule.",
        "verify": [("eval", "5-2", "3"), ("eval", "2-5", "-3")],
    },
    {
        "concept": "int", "level": 4, "type": "step_by_step",
        "objective": "Break a multi-operation integer expression into ordered steps.",
        "stem": "Evaluate -3 x (-4 + 7) - (-5) one step at a time.",
        "steps": [
            {"prompt": "Work out the bracket: -4 + 7 = ?", "answer": "3", "hint": "Start at -4 and move 7 to the right."},
            {"prompt": "Multiply -3 by your result from step 1.", "answer": "-9", "hint": "Positive times negative is negative."},
            {"prompt": "Subtract -5 from your result from step 2.", "answer": "-4", "hint": "Subtracting -5 is the same as adding 5."},
        ],
        "hint": "Brackets first, then multiplication, then subtraction.",
        "explanation": "-4 + 7 = 3; -3 x 3 = -9; -9 - (-5) = -9 + 5 = -4.",
        "verify": [("eval", "-4+7", "3"), ("eval", "-3*3", "-9"), ("eval", "-9-(-5)", "-4")],
    },
    # ---- L5 Evaluate
    {
        "concept": "int", "level": 5, "type": "mcq",
        "objective": "Evaluate a student's reasoning about subtracting a negative.",
        "stem": "Asha says: '(-7) - (-7) = 14, because minus minus makes plus.' Evaluate her reasoning.",
        "correct": "Incorrect: subtracting -7 means adding 7, so (-7) + 7 = 0.",
        "distractors": [
            ("Correct: subtracting a negative always doubles the number.", "Believed subtracting a negative doubles the value"),
            ("Incorrect: the answer is -14 because both numbers are negative.", "Added magnitudes and kept the negative sign"),
            ("Correct: subtracting equal numbers gives their sum.", "Confused 'equal numbers cancel' with 'equal numbers add'"),
        ],
        "hint": "Subtracting a number from itself always gives the same result, whatever the sign.",
        "explanation": "'Minus minus makes plus' turns the subtraction into addition, but it gives (-7) + 7 = 0, not 14. Any number minus itself is 0.",
        "verify": [("eval", "(-7)-(-7)", "0")],
    },
    {
        "concept": "int", "level": 5, "type": "assertion_reasoning",
        "objective": "Judge an assertion and its reason about odd powers of -1.",
        "stem": "Assertion (A): (-1) to the power 101 equals -1.\nReason (R): A negative integer raised to an odd power is negative.\nWhich option is correct?",
        **_ar(0),
        "hint": "Is the reason a general rule that produces the assertion?",
        "explanation": "R is a true general rule, and applying it to -1 with the odd power 101 gives -1, so R explains A.",
        "verify": [("eval", "(-1)**101", "-1")],
    },
    {
        "concept": "int", "level": 5, "type": "mcq",
        "objective": "Evaluate a computed answer using sign reasoning.",
        "stem": "A student computed (-15) / (-3) x (-2), working left to right, and got 10. Which judgement is best?",
        "correct": "Wrong: three negative numbers are involved, so the result must be negative; the answer is -10.",
        "distractors": [
            ("Correct: (-15) / (-3) = 5 and 5 x 2 = 10.", "Dropped the negative sign of -2"),
            ("Wrong: the answer should be -30.", "Multiplied -15 by -2 instead of dividing first"),
            ("Wrong: the answer should be -2.5, because the product -3 x -2 is done first.", "Changed the order of operations"),
        ],
        "hint": "Divide first, then multiply, and track the sign at each step.",
        "explanation": "(-15) / (-3) = 5, then 5 x (-2) = -10. The student lost the negative sign on the last factor.",
        "verify": [("eval", "(-15)/(-3)*(-2)", "-10")],
    },
    # =====================================================================
    # ALGEBRAIC EXPRESSIONS (Class 7)
    # =====================================================================
    # ---- L1 Remember
    {
        "concept": "alg", "level": 1, "type": "mcq",
        "objective": "Identify the coefficient of a term.",
        "stem": "In the expression 5x^2 + 3x - 7, what is the coefficient of x?",
        "correct": "3",
        "distractors": [
            ("5", "Picked the coefficient of x^2"),
            ("-7", "Picked the constant term"),
            ("x", "Named the variable instead of its numerical factor"),
        ],
        "hint": "The coefficient is the number multiplying the variable part.",
        "explanation": "The term 3x has numerical factor 3, so the coefficient of x is 3.",
        "conceptual": True,
    },
    {
        "concept": "alg", "level": 1, "type": "true_false",
        "objective": "Recall the definition of like terms.",
        "stem": "True or false: 3x and 3y are like terms.",
        "answer": False,
        "hint": "Like terms have exactly the same variable part.",
        "explanation": "The variable parts x and y are different, so 3x and 3y are unlike terms even though the coefficients match.",
        "conceptual": True,
    },
    {
        "concept": "alg", "level": 1, "type": "fill_blank",
        "objective": "Name a term without a variable.",
        "stem": "In the expression 4a + 9, the term 9 is called a ____ term.",
        "accepted": ["constant"],
        "hint": "Its value never changes whatever a is.",
        "explanation": "A term with no variable is a constant term.",
        "conceptual": True,
    },
    # ---- L2 Understand
    {
        "concept": "alg", "level": 2, "type": "mcq",
        "objective": "Classify an expression by its number of terms.",
        "stem": "Which of the following is a binomial?",
        "correct": "4x + 5y",
        "distractors": [
            ("7x", "Counted a single term as two"),
            ("3x^2 - 2x + 1", "Counted three terms as two"),
            ("9", "Thought a constant is a binomial"),
        ],
        "hint": "A binomial has exactly two terms.",
        "explanation": "4x + 5y has two terms (4x and 5y). 7x and 9 are monomials and 3x^2 - 2x + 1 is a trinomial.",
        "conceptual": True,
    },
    {
        "concept": "alg", "level": 2, "type": "mcq",
        "objective": "Recognise like terms.",
        "stem": "Which pair of terms are like terms?",
        "correct": "3a^2b and -5a^2b",
        "distractors": [
            ("2xy and 2x", "Matched coefficients instead of variable parts"),
            ("4x^2 and 4x", "Ignored the different powers of x"),
            ("7p and 7q", "Matched coefficients instead of variable parts"),
        ],
        "hint": "Compare the variable parts, including powers. Coefficients can differ.",
        "explanation": "3a^2b and -5a^2b have the same variable part a^2b, so they are like terms.",
        "conceptual": True,
    },
    {
        "concept": "alg", "level": 2, "type": "true_false",
        "objective": "Understand combining like terms.",
        "stem": "True or false: 2x + 3x simplifies to 5x^2.",
        "answer": False,
        "hint": "Adding like terms changes the coefficient, not the power.",
        "explanation": "2x + 3x = (2 + 3)x = 5x. The power of x stays 1; it is not squared.",
        "verify": [("equiv", "2*x+3*x", "5*x", True), ("equiv", "2*x+3*x", "5*x**2", False)],
    },
    # ---- L3 Apply
    {
        "concept": "alg", "level": 3, "type": "numerical",
        "objective": "Evaluate an expression by substitution.",
        "stem": "Find the value of 3x^2 - 2x + 1 when x = 2.",
        "answer": "9", "tolerance": 0,
        "hint": "Substitute 2 for x and square first: 3 x 2^2.",
        "explanation": "3(2)^2 - 2(2) + 1 = 12 - 4 + 1 = 9.",
        "verify": [("eval", "3*2**2-2*2+1", "9")],
    },
    {
        "concept": "alg", "level": 3, "type": "mcq",
        "objective": "Add two algebraic expressions.",
        "stem": "Simplify (4a + 3b) + (2a - 5b).",
        "correct": "6a - 2b",
        "distractors": [
            ("6a + 8b", "Ignored the negative sign of -5b"),
            ("2a - 2b", "Subtracted the a terms"),
            ("4ab", "Added every coefficient and joined unlike terms"),
        ],
        "hint": "Group the a terms together and the b terms together.",
        "explanation": "a terms: 4a + 2a = 6a. b terms: 3b - 5b = -2b. So the sum is 6a - 2b.",
        "verify": [("equiv", "(4*a+3*b)+(2*a-5*b)", "6*a-2*b", True)],
    },
    {
        "concept": "alg", "level": 3, "type": "fill_blank",
        "objective": "Subtract one expression from another.",
        "stem": "Subtract (3x - 2) from (5x + 4). The result is ____.",
        "accepted": ["2x+6", "2x + 6", "6+2x"],
        "hint": "Subtracting a bracket changes the sign of every term inside it.",
        "explanation": "(5x + 4) - (3x - 2) = 5x + 4 - 3x + 2 = 2x + 6.",
        "verify": [("equiv", "(5*x+4)-(3*x-2)", "2*x+6", True)],
    },
    # ---- L4 Analyze
    {
        "concept": "alg", "level": 4, "type": "mcq",
        "objective": "Locate the error in a simplification.",
        "stem": "Ravi simplified 2(x + 3) - (x - 4) as: 2x + 6 - x - 4 = x + 2. Which step contains the error?",
        "correct": "Removing the bracket (x - 4): the -4 should become +4.",
        "distractors": [
            ("Expanding 2(x + 3) into 2x + 6.", "Doubted a correct expansion"),
            ("Combining 2x and -x to get x.", "Doubted a correct combination"),
            ("There is no error; x + 2 is correct.", "Did not check the sign change when removing a bracket"),
        ],
        "hint": "Check what happens to each term inside the bracket that follows the minus sign.",
        "explanation": "-(x - 4) = -x + 4, not -x - 4. So the correct result is 2x + 6 - x + 4 = x + 10.",
        "verify": [("equiv", "2*(x+3)-(x-4)", "x+10", True), ("equiv", "2*(x+3)-(x-4)", "x+2", False)],
    },
    {
        "concept": "alg", "level": 4, "type": "multi_select",
        "objective": "Identify equivalent expressions.",
        "stem": "Select ALL expressions equivalent to 3(x + 2) - x.",
        "correct_set": ["2x + 6", "2(x + 3)"],
        "distractors": [
            ("3x + 2 - x", "Multiplied only the first term of the bracket by 3"),
            ("4x + 6", "Added x instead of subtracting it"),
        ],
        "hint": "Expand and simplify 3(x + 2) - x first, then compare each option.",
        "explanation": "3(x + 2) - x = 3x + 6 - x = 2x + 6, which equals 2(x + 3). The option 3x + 2 - x equals 2x + 2, and 4x + 6 is different.",
        "verify": [
            ("equiv", "3*(x+2)-x", "2*x+6", True), ("equiv", "3*(x+2)-x", "2*(x+3)", True),
            ("equiv", "3*(x+2)-x", "3*x+2-x", False), ("equiv", "3*(x+2)-x", "4*x+6", False),
        ],
    },
    {
        "concept": "alg", "level": 4, "type": "mcq",
        "objective": "Form and justify an expression for a perimeter.",
        "stem": "A rectangle has length (3x + 2) and width (x + 4). Which expression gives its perimeter?",
        "correct": "8x + 12",
        "distractors": [
            ("3x^2 + 14x + 8", "Found the area instead of the perimeter"),
            ("4x + 6", "Found half the perimeter (length + width only)"),
            ("7x + 8", "Doubled the length but not the width"),
        ],
        "hint": "Perimeter = 2 x (length + width).",
        "explanation": "Perimeter = 2[(3x + 2) + (x + 4)] = 2(4x + 6) = 8x + 12.",
        "verify": [("equiv", "2*((3*x+2)+(x+4))", "8*x+12", True)],
    },
    # ---- L5 Evaluate
    {
        "concept": "alg", "level": 5, "type": "mcq",
        "objective": "Judge two students' simplifications.",
        "stem": "Priya and Kiran simplify 4(2x - 3) + 2(x + 5). Priya gets 10x - 2. Kiran gets 10x + 22. Who is correct?",
        "correct": "Priya: 8x - 12 + 2x + 10 = 10x - 2.",
        "distractors": [
            ("Kiran: the constants -12 and 10 should be added as 12 + 10.", "Dropped the negative sign when expanding 4(2x - 3)"),
            ("Both are wrong; the answer is 10x + 2.", "Mis-added the constants -12 and +10"),
            ("Both are correct because the coefficient of x is the same.", "Compared only the coefficient of x"),
        ],
        "hint": "Expand each bracket carefully, keeping the sign of every product.",
        "explanation": "4(2x - 3) = 8x - 12 and 2(x + 5) = 2x + 10. Adding gives 10x - 2, so Priya is correct. Kiran lost the minus sign on -12.",
        "verify": [("equiv", "4*(2*x-3)+2*(x+5)", "10*x-2", True), ("equiv", "4*(2*x-3)+2*(x+5)", "10*x+22", False)],
    },
    {
        "concept": "alg", "level": 5, "type": "assertion_reasoning",
        "objective": "Judge a false assertion that misuses the distributive law.",
        "stem": "Assertion (A): The expressions 3(x + 4) and 3x + 4 are equal for every value of x.\nReason (R): Multiplication distributes over addition.\nWhich option is correct?",
        **_ar(3),
        "hint": "Expand 3(x + 4) fully and compare it with 3x + 4.",
        "explanation": "3(x + 4) = 3x + 12, which differs from 3x + 4 by 8 for every x, so A is false. R is a true rule (it is the reason 3(x + 4) = 3x + 12).",
        "verify": [("equiv", "3*(x+4)", "3*x+4", False), ("equiv", "3*(x+4)", "3*x+12", True)],
    },
    {
        "concept": "alg", "level": 5, "type": "mcq",
        "objective": "Evaluate a claim about squaring a sum with a counterexample.",
        "stem": "Meena claims that (a + b)^2 = a^2 + b^2 for all numbers. Which evaluation is best?",
        "correct": "False: for a = 1, b = 2, (a + b)^2 = 9 but a^2 + b^2 = 5.",
        "distractors": [
            ("True: squaring distributes over addition.", "Assumed squaring distributes over addition"),
            ("True: it works for a = 1, b = 0, so it always works.", "Generalised from a single special case"),
            ("False: the correct result is a^2 - b^2.", "Confused (a + b)^2 with the difference of squares"),
        ],
        "hint": "Try small numbers for a and b and compare both sides.",
        "explanation": "With a = 1 and b = 2, (1 + 2)^2 = 9 but 1^2 + 2^2 = 5. The correct expansion is a^2 + 2ab + b^2.",
        "verify": [("eval", "(1+2)**2", "9"), ("eval", "1**2+2**2", "5"), ("equiv", "(a+b)**2", "a**2+2*a*b+b**2", True)],
    },
    # =====================================================================
    # LINEAR EQUATIONS (Class 8)
    # =====================================================================
    # ---- L1 Remember
    {
        "concept": "lin", "level": 1, "type": "mcq",
        "objective": "Identify a linear equation in one variable.",
        "stem": "Which of the following is a linear equation in one variable?",
        "correct": "2x + 3 = 9",
        "distractors": [
            ("x^2 + 1 = 5", "Did not notice the variable is squared"),
            ("x + y = 4", "Counted an equation with two variables"),
            ("1/x = 3", "Did not notice the variable is in the denominator"),
        ],
        "hint": "The variable must appear to the power 1 only, and there must be just one variable.",
        "explanation": "2x + 3 = 9 has one variable with power 1. x^2 + 1 = 5 is quadratic, x + y = 4 has two variables, and 1/x = 3 is not linear in x.",
        "conceptual": True,
    },
    {
        "concept": "lin", "level": 1, "type": "true_false",
        "objective": "Recall the standard form of a linear equation.",
        "stem": "True or false: a linear equation in one variable can be written in the form ax + b = 0 with a not equal to 0.",
        "answer": True,
        "hint": "Move every term to one side.",
        "explanation": "Any linear equation in one variable can be rearranged to ax + b = 0, where a is not 0.",
        "conceptual": True,
    },
    {
        "concept": "lin", "level": 1, "type": "fill_blank",
        "objective": "Recall the term for the value that satisfies an equation.",
        "stem": "The value of the variable that makes both sides of an equation equal is called its ____.",
        "accepted": ["solution", "root"],
        "hint": "It is what you find when you solve the equation.",
        "explanation": "A value of the variable that makes both sides equal is called a solution (or root) of the equation.",
        "conceptual": True,
    },
    # ---- L2 Understand
    {
        "concept": "lin", "level": 2, "type": "mcq",
        "objective": "Choose the inverse operation to isolate the variable.",
        "stem": "To solve x + 7 = 12, what should you do to both sides?",
        "correct": "Subtract 7",
        "distractors": [
            ("Add 7", "Used the same operation instead of the inverse"),
            ("Multiply by 7", "Mixed up addition with multiplication"),
            ("Divide by 7", "Mixed up addition with multiplication"),
        ],
        "hint": "Undo the +7 with its opposite operation.",
        "explanation": "Subtracting 7 from both sides gives x = 5.",
        "verify": [("solve", "x + 7 = 12", "x", "5")],
    },
    {
        "concept": "lin", "level": 2, "type": "true_false",
        "objective": "Understand that equal operations on both sides preserve the solution.",
        "stem": "True or false: if you add the same number to both sides of an equation, the solution does not change.",
        "answer": True,
        "hint": "Think of a balanced scale.",
        "explanation": "Adding the same amount to both sides keeps the equation balanced, so the solution is unchanged.",
        "conceptual": True,
    },
    {
        "concept": "lin", "level": 2, "type": "mcq",
        "objective": "Recognise equivalent equations.",
        "stem": "Which equation has the same solution as 2x = 10?",
        "correct": "x - 5 = 0",
        "distractors": [
            ("x + 2 = 10", "Applied the operation to only one term"),
            ("x / 2 = 10", "Multiplied instead of divided"),
            ("x + 5 = 0", "Sign error when moving 5 across the equals sign"),
        ],
        "hint": "Solve 2x = 10 first, then test each option with that value.",
        "explanation": "2x = 10 gives x = 5. Only x - 5 = 0 has the solution x = 5.",
        "verify": [
            ("solve", "2*x = 10", "x", "5"), ("solve", "x - 5 = 0", "x", "5"),
            ("solve", "x + 2 = 10", "x", "8"), ("solve", "x/2 = 10", "x", "20"), ("solve", "x + 5 = 0", "x", "-5"),
        ],
    },
    # ---- L3 Apply
    {
        "concept": "lin", "level": 3, "type": "numerical",
        "objective": "Solve a two-step linear equation.",
        "stem": "Solve 3x + 5 = 20. What is x?",
        "answer": "5", "tolerance": 0,
        "hint": "Subtract 5 from both sides first, then divide by 3.",
        "explanation": "3x = 20 - 5 = 15, so x = 15 / 3 = 5.",
        "verify": [("solve", "3*x + 5 = 20", "x", "5")],
    },
    {
        "concept": "lin", "level": 3, "type": "numerical",
        "objective": "Solve an equation with a bracket.",
        "stem": "Solve 2(x - 3) = 10. What is x?",
        "answer": "8", "tolerance": 0,
        "hint": "Either divide both sides by 2 first, or expand the bracket.",
        "explanation": "Dividing by 2 gives x - 3 = 5, so x = 8. (Expanding: 2x - 6 = 10, 2x = 16, x = 8.)",
        "verify": [("solve", "2*(x - 3) = 10", "x", "8")],
    },
    {
        "concept": "lin", "level": 3, "type": "mcq",
        "objective": "Solve an equation with a fraction.",
        "stem": "Solve x/4 + 2 = 6.",
        "correct": "x = 16",
        "distractors": [
            ("x = 32", "Added 2 instead of subtracting it"),
            ("x = 4", "Forgot to multiply by 4 at the end"),
            ("x = 24", "Multiplied 6 by 4 without subtracting 2 first"),
        ],
        "hint": "Subtract 2 from both sides first, then multiply by 4.",
        "explanation": "x/4 = 6 - 2 = 4, so x = 4 x 4 = 16.",
        "verify": [("solve", "x/4 + 2 = 6", "x", "16")],
    },
    # ---- L4 Analyze
    {
        "concept": "lin", "level": 4, "type": "mcq",
        "objective": "Find the faulty step in a solution.",
        "stem": "A student solves 5x - 3 = 2x + 9 like this: subtract 2x: 3x - 3 = 9; subtract 3: 3x = 6; divide by 3: x = 2. Which step is wrong?",
        "correct": "Subtracting 3 instead of adding 3 to remove the -3.",
        "distractors": [
            ("Subtracting 2x from both sides.", "Doubted a valid step"),
            ("Dividing both sides by 3.", "Doubted a valid step"),
            ("There is no error; x = 2 is correct.", "Did not check the answer by substitution"),
        ],
        "hint": "Substitute x = 2 back into the original equation and see if both sides match.",
        "explanation": "To remove -3 you add 3: 3x = 12, so x = 4. Check: 5(4) - 3 = 17 and 2(4) + 9 = 17.",
        "verify": [("solve", "5*x - 3 = 2*x + 9", "x", "4")],
    },
    {
        "concept": "lin", "level": 4, "type": "multi_select",
        "objective": "Identify equations that share a solution.",
        "stem": "Select ALL equations whose solution is x = 3.",
        "correct_set": ["2x + 1 = 7", "4x = 12"],
        "distractors": [
            ("x - 5 = 2", "Added 5 to the wrong side and got x = 7"),
            ("3x - 2 = 8", "Arithmetic slip; the solution is not a whole number"),
        ],
        "hint": "Substitute x = 3 into each equation and check both sides.",
        "explanation": "2(3) + 1 = 7 and 4(3) = 12 both hold. For x - 5 = 2 the solution is 7, and for 3x - 2 = 8 it is 10/3.",
        "verify": [
            ("solve", "2*x + 1 = 7", "x", "3"), ("solve", "4*x = 12", "x", "3"),
            ("solve", "x - 5 = 2", "x", "7"), ("solve", "3*x - 2 = 8", "x", "10/3"),
        ],
    },
    {
        "concept": "lin", "level": 4, "type": "step_by_step",
        "objective": "Solve an equation with variables on both sides in ordered steps.",
        "stem": "Solve 4(x + 2) = 3x + 14 one step at a time.",
        "steps": [
            {"prompt": "Expand the bracket: 4(x + 2) = 4x + ?", "answer": "8", "hint": "Multiply 4 by both x and 2."},
            {"prompt": "Move the x terms to one side: x = 14 - ?", "answer": "8", "hint": "Subtract 3x and subtract 8 from both sides."},
            {"prompt": "So x = ?", "answer": "6", "hint": "Finish the subtraction."},
        ],
        "hint": "Expand first, then collect the x terms on one side.",
        "explanation": "4x + 8 = 3x + 14, so x = 14 - 8 = 6. Check: 4(6 + 2) = 32 and 3(6) + 14 = 32.",
        "verify": [("solve", "4*(x + 2) = 3*x + 14", "x", "6")],
    },
    # ---- L5 Evaluate
    {
        "concept": "lin", "level": 5, "type": "mcq",
        "objective": "Evaluate two valid solution methods.",
        "stem": "To solve 3(x - 1) = 12, Method 1 divides both sides by 3 first (x - 1 = 4, so x = 5). Method 2 expands first (3x - 3 = 12, 3x = 15, x = 5). Evaluate the two methods.",
        "correct": "Both are valid and give x = 5; Method 1 takes fewer steps.",
        "distractors": [
            ("Only Method 1 is valid; expanding a bracket is not allowed.", "Believed brackets must never be expanded"),
            ("Only Method 2 is valid; you cannot divide before expanding.", "Believed you must always expand first"),
            ("The methods give different answers, so one must be wrong.", "Did not carry out both methods to the end"),
        ],
        "hint": "Solve each method to the end and compare the results.",
        "explanation": "Both methods keep the equation balanced and give x = 5. Dividing first avoids expanding, so it is shorter here.",
        "verify": [("solve", "3*(x - 1) = 12", "x", "5")],
    },
    {
        "concept": "lin", "level": 5, "type": "mcq",
        "objective": "Evaluate a claimed solution to a word problem.",
        "stem": "The sum of three consecutive integers is 72. Aarav says they are 24, 25 and 26. Evaluate his answer.",
        "correct": "Incorrect: 24 + 25 + 26 = 75. Solving x + (x + 1) + (x + 2) = 72 gives x = 23, so the numbers are 23, 24, 25.",
        "distractors": [
            ("Correct: 24 + 25 + 26 = 72.", "Mis-added the three numbers"),
            ("Incorrect: they should be 22, 23, 24.", "Guessed without forming the equation"),
            ("Incorrect: they should all be 24.", "Confused consecutive integers with equal integers"),
        ],
        "hint": "Add his three numbers, then set up and solve x + (x + 1) + (x + 2) = 72.",
        "explanation": "3x + 3 = 72, so 3x = 69 and x = 23. The integers are 23, 24, 25 and 23 + 24 + 25 = 72.",
        "verify": [("solve", "x + (x + 1) + (x + 2) = 72", "x", "23"), ("eval", "24+25+26", "75")],
    },
    {
        "concept": "lin", "level": 5, "type": "assertion_reasoning",
        "objective": "Judge a claim about an equation with no solution.",
        "stem": "Assertion (A): The equation 2x + 3 = 2x + 5 has no solution.\nReason (R): Subtracting 2x from both sides gives 3 = 5, which is false.\nWhich option is correct?",
        **_ar(0),
        "hint": "What does reaching a false statement like 3 = 5 tell you about the equation?",
        "explanation": "Subtracting 2x from both sides leaves 3 = 5, which is never true, so no value of x works. R is the reason A holds.",
        "verify": [("solve", "2*x + 3 = 2*x + 5", "x", "none")],
    },
]
