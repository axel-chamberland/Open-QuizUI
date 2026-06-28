# QuizUI
This is tool / action function for displaying multiple choice quizzes inside Open WebUI.
As Frontend and Backend are seperate, it can easily be adapted to work outside Open WebUI.

## Usage
There are two options:
- Put the tool code in Workspace > Tools > New Tool.
- Put the function code in Admin Panel > Functions > New Function.
While the tool will work, I recommend using the action function since it is easier for an LLM to write quizzes naturally then by using a specific structure format via tool calling.

The function is triggered by pressing the action button under an LLM's message.

## Recommended Models

- Any model will work. However, some models such as Qwen3.5 9B make formatting mistakes and doubt themselves, causing duplications. Gemma usually has better formatting.
- Currently, answers keys in a markdown table are not supported. Most other formatting should work (adjust your prompt as needed).
- Supported languages: Parsing looks for French and English keywords (Question, Answer, A, Réponse, R). If you use another language, you can update the parsing in the code to add keywords or modify your prompt.
