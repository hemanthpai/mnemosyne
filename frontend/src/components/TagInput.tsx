import React, { KeyboardEvent, useState } from 'react';

interface TagInputProps {
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  className?: string;
}

const TagInput: React.FC<TagInputProps> = ({
  value = [],
  onChange,
  placeholder = "Type and press space to add...",
  className = ""
}) => {
  const [inputValue, setInputValue] = useState('');

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === ' ' && inputValue.trim()) {
      e.preventDefault();
      const newTag = inputValue.trim();
      if (!value.includes(newTag)) {
        onChange([...value, newTag]);
      }
      setInputValue('');
    } else if (e.key === 'Backspace' && !inputValue && value.length > 0) {
      // Remove last tag when backspace is pressed on empty input
      onChange(value.slice(0, -1));
    }
  };

  const removeTag = (indexToRemove: number) => {
    onChange(value.filter((_, index) => index !== indexToRemove));
  };

  return (
    <div className={`border border-gray-300 rounded-md p-2 min-h-[2.5rem] flex flex-wrap gap-2 items-center ${className}`}>
      {value.map((tag, index) => (
        <span
          key={index}
          className="inline-flex items-center px-2 py-1 bg-blue-100 text-blue-800 text-sm rounded-md"
        >
          {tag}
          <button
            type="button"
            onClick={() => removeTag(index)}
            className="ml-1 text-blue-600 hover:text-blue-800 focus:outline-none"
          >
            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </button>
        </span>
      ))}
      <input
        type="text"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={value.length === 0 ? placeholder : ""}
        className="flex-1 min-w-[120px] outline-none bg-transparent"
      />
    </div>
  );
};

export default TagInput;