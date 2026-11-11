---
title: "Clean Code: Lessons Every Beginner Developer Should Practise"
date: "2026-11-07"
published: true
category: "Engineering"
---

# Clean Code: Lessons Every Beginner Developer Should Practise

**Clean Code** by Robert C. Martin is a well-known software engineering book that argues code should be understandable, maintainable, and carefully organised. Its examples and opinions are worth thinking about, although developers should adapt principles to their language, team, and project.

For beginners, the most useful lesson is simple: code is read by people as well as executed by computers.

## Five habits to practise

1. **Use meaningful names.** A variable called `total_price` communicates more than `x`.
2. **Keep functions focused.** A function should have one clear responsibility whenever practical.
3. **Avoid unnecessary duplication.** If the same logic appears repeatedly, consider whether a small reusable function would help.
4. **Handle errors deliberately.** Validate inputs and give useful error messages instead of allowing confusing failures.
5. **Refactor gradually.** Improve code in small steps and run tests after each change.

## Example

Instead of writing a vague function named `do_it()`, choose a name such as `calculate_order_total()`. The name tells another developer what to expect.

Clean code is not code with the fewest lines. Short code can still be confusing. The goal is clarity, correctness, and ease of change.

**Practice:** Pick one function in your current project. Improve its names, make its purpose clearer, and run its tests again.
