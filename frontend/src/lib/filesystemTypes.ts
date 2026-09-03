export type DirEntry = {
    name: string;
    path: string;
  };
  
  export type BrowseResult = {
    path: string | null;
    parent: string | null;
    entries: DirEntry[];
    roots: DirEntry[];
  };