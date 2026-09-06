# Open-QuizUI Wiki

Documentation for [Open-QuizUI](https://github.com/axel-chamberland/Open-QuizUI).

Open-QuizUI is an Open WebUI function that turns LLM-generated quizzes into an interactive UI.


## Tool or Action Function

Open-QuizUI can be used as either a Tool or an Action.

Type | Pros | Cons
-- | -- | --
Tool | Automatic — the model decides when to display a quiz. The structured output makes the quiz predictable and easy for Open-QuizUI to parse. | Less user control; depends on the model choosing to call it. Strict JSON formatting makes generation more demanding for small models.
Action | User has direct control over when to display a quiz, can modify the message, and regenerate the quiz as needed. | Requires manually triggering it from the message actions. The quiz format may not be recognized


## Pages

* [[Getting Started]]
* [[Usage]]
* [[Formatting]]
* [[Customization]]
* [[Troubleshooting]]
* [[Development]]
* [[Contributing]]