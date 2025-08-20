## Initial Request

In preparation for the definitions of new players, I want to make sure the logic for OllamaPlayer is distributed to separate the following functionalities:
1. Make a move: a player class method that when given the phase and messages as input (and maybe state, but it may already be an attribute and unnecessary), returns both the new history entry, as well as the parsed move and anything else that is relevant as this stage, as the output
2. Save the pickle file: the same logic for saving the 'turn_###.pkl' file, but recieves the file name prefix (i.e., "turn") as input (as well as any relevant data that can't be derived from self attributes)
3. End game turn: pretty self explanatory, this method is also where the previous method (2) is used to write `turn_###.pkl`

## Majority Classes

Let me describe the new logic I want to include, it consists of 2 new classes:

1. OllamaVoter: techincally not a player, it acts exactly as an OllamaPlayer would, but it has only a one attempt and its results are saved to `v{i}_###.pkl` 
But a key difference between voters and player is the moves a voter makes are not immediately used to advance the turn, but are used by the next class
2. MajorityPlayer: It's not an actual agent, instead it uses the parsed moves from voters, and chooses the move made by the majority (tie-breaking is an arbitrary decision), unless none of the voters made a valid move and then the game terminates with an error. It uses the 'max_tries' parameter differently. Assuming max_tries=3, rather than having 3 attempts, it selects the majority of 3 voters, each having only 1 attempt
