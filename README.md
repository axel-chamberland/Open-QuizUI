# QuizUI
This is tool / action function for displaying multiple choice quizzes inside Open WebUI.
As Frontend and Backend are seperate, it can easily be adapted to work outside Open WebUI.

## Usage
There are two options:
- Put the tool code in Workspace > Tools > New Tool.
- Put the function code in Admin Panel > Functions > New Function.

> For the UI to render LaTeX with MathJax, you must turn it on in the settings (gear icon)

While the tool will work, I recommend using the action function since it is easier for an LLM to write quizzes naturally then by using a specific structure format via tool calling.

The function is triggered by pressing the action button under an LLM's message.

## Recommendations

- Any model will work. However, some models such as Qwen3.5 9B can make formatting mistakes and doubt themselves, causing duplications on complicated quizzes. Gemma usually has better formatting.
- Currently, answer keys in a markdown table are not supported. Most other formatting should work (adjust your prompt as needed).
- Supported languages: Parsing looks for French and English keywords (Question, Answer, A, Réponse, R). If you use another language, you can update the parsing in the code to add keywords or modify your prompt.
- For the function to work, BOTH the questions and the answers must be in the same message: if the LLM gives them in two different messages, you can edit the LLM's first message and paste the answer key there.
