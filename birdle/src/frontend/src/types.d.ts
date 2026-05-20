type Bird = {
  id: string; // or UUID if using something like 'uuid' type
  common_name: string;
  scientific_name: string;
  order: string,
  family: string,
  genus: string,
};

type Guess = {
    round_id: string;
    guess_id: string
};

type FullGuess = {
    guess: Guess,
    bird: Bird,
}

export { Bird, Guess, FullGuess }
