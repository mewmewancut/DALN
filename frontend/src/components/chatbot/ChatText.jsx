export default function ChatText({ text }) {
  return (
    <p className="genie-text">
      {text
        .split(/(\*\*[^*\n]+\*\*)/g)
        .map((part, index) =>
          part.startsWith("**") && part.endsWith("**") ? (
            <strong key={index}>{part.slice(2, -2)}</strong>
          ) : (
            part
          ),
        )}
    </p>
  );
}
