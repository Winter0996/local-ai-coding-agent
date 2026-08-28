type DiffViewProps = {
    diff: string;
  };
  
  export function DiffView({ diff }: DiffViewProps) {
    const lines = diff.split("\n");
  
    return (
      <pre className="diff-view">
        {lines.map((line, index) => {
          let className = "diff-line";
          if (line.startsWith("+++") || line.startsWith("---")) {
            className += " diff-line-header";
          } else if (line.startsWith("+")) {
            className += " diff-line-add";
          } else if (line.startsWith("-")) {
            className += " diff-line-remove";
          } else if (line.startsWith("@@")) {
            className += " diff-line-hunk";
          }
          return (
            <div key={index} className={className}>
              {line || " "}
            </div>
          );
        })}
      </pre>
    );
  }