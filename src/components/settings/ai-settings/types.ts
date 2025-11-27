export interface AIProvider {
  id: string;
  name: string;
  description: string;
  secret_name: string;
  has_secret: boolean;
}

export interface AIModel {
  id: string;
  name: string;
  type: string;
}
