export interface Memory {
  id: string;
  content: string;
  tags: string[];
  createdAt: string;
  updatedAt: string;
}

export interface StoreMemoryRequest {
  content: string;
  tags?: string[];
}

export interface FetchMemoriesQuery {
  query?: string;
  tags?: string;
}
