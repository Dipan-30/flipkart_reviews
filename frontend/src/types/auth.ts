export interface User {
  user_id: string;
  name: string;
  email: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  name: string;
  email: string;
}
