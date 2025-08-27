export interface Answer {
  page: number;
  text: string;
  images?: string[]; // now always an array of strings
}
