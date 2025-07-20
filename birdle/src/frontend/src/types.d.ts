type Bird = {
  id: string; // or UUID if using something like 'uuid' type
  common_name: string;
  scientific_name: string;
  order: string;
  family: string;
  genus: string;
  audio_path: string;
  image_path: string;
};

export { Bird }