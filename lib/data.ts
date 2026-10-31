// All data here is DEMO / sample content for prototyping. Nothing is computed from real learners.
export const boards = ["Telangana State Board", "ICSE"] as const;
export const classes = [6, 7, 8, 9, 10];
export const languages = ["English", "Telugu", "Hindi"];
export const subjects = ["Mathematics", "Science", "Social Studies", "English", "Telugu", "Hindi"];
export const roles = [
  { id: "student", label: "Student", desc: "Follow a guided path through your class syllabus.", href: "/dashboard" },
  { id: "self", label: "Self-Learner", desc: "Pick topics freely and learn at your own pace.", href: "/dashboard" },
  { id: "teacher", label: "Teacher", desc: "See class gaps, build assessments, plan remediation.", href: "/teacher" },
  { id: "parent", label: "Parent", desc: "Follow your child's progress and upcoming tests.", href: "/parent" },
];
export const chapters = [
  { title: "Rational Numbers", mins: 90, pre: ["Fractions", "Integers"], obj: ["Compare and order rational numbers", "Represent them on a number line"] },
  { title: "Linear Equations in One Variable", mins: 120, pre: ["Algebraic Expressions"], obj: ["Solve equations with variables on one side", "Form equations from word statements"] },
  { title: "Understanding Quadrilaterals", mins: 100, pre: ["Basic Geometry"], obj: ["Classify quadrilaterals", "Use angle-sum property"] },
  { title: "Data Handling", mins: 80, pre: ["Fractions"], obj: ["Read and group data", "Interpret bar graphs and pie charts"] },
];
export type NodeState = "mastered" | "weak" | "next" | "locked";
export const mapNodes: { id: string; level: number; pre: string[]; state: NodeState }[] = [
  { id: "Integers", level: 0, pre: [], state: "mastered" },
  { id: "Fractions", level: 0, pre: [], state: "mastered" },
  { id: "Algebraic Expressions", level: 1, pre: ["Integers"], state: "weak" },
  { id: "Linear Equations", level: 2, pre: ["Algebraic Expressions"], state: "next" },
  { id: "Word Problems", level: 3, pre: ["Linear Equations"], state: "locked" },
  { id: "Graphing Equations", level: 3, pre: ["Linear Equations"], state: "locked" },
];
export const questions = [
  { q: "Solve: 2x + 5 = 17", opts: ["x = 5", "x = 6", "x = 7", "x = 11"], a: 1, hint: "Subtract 5 from both sides first.", why: "2x = 12, so x = 6." },
  { q: "Solve: 3(x − 2) = 15", opts: ["x = 5", "x = 6", "x = 7", "x = 9"], a: 2, hint: "Divide both sides by 3, then add 2.", why: "x − 2 = 5, so x = 7." },
  { q: "The sum of two consecutive integers is 41. What is the smaller one?", opts: ["19", "20", "21", "22"], a: 1, hint: "Call them x and x + 1.", why: "2x + 1 = 41, so x = 20." },
  { q: "Solve: x/4 + 3 = 7", opts: ["x = 1", "x = 10", "x = 16", "x = 28"], a: 2, hint: "Subtract 3, then multiply by 4.", why: "x/4 = 4, so x = 16." },
];
