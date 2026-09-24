import { forwardRef, ButtonHTMLAttributes } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'outline' | 'ghost' | 'link' | 'ink' | 'hairline';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  fullWidth?: boolean;
}

const variantClasses = {
  // Signature persimmon red CTA
  primary: 'bg-mistral-red text-purewhite hover:bg-mistral-red-deep',
  secondary: 'bg-mistral-band border border-mistral-border hover:bg-mistral-inset text-mistral-ink',
  danger: 'bg-mistral-red-deep text-purewhite hover:opacity-90',
  outline: 'border border-mistral-border-strong hover:border-mistral-ink text-mistral-ink bg-transparent',
  ghost: 'text-mistral-muted hover:bg-mistral-band hover:text-mistral-ink bg-transparent',
  link: 'text-mistral-red hover:text-mistral-red-deep bg-transparent underline',
  ink: 'bg-mistral-ink text-mistral-surface hover:bg-mistral-red',
  hairline: 'border border-mistral-border-strong bg-white text-mistral-ink hover:border-mistral-ink',
};

const sizeClasses = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-base',
  lg: 'px-6 py-3 text-lg',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className = '',
      variant = 'primary',
      size = 'md',
      isLoading = false,
      fullWidth = false,
      disabled,
      children,
      ...props
    },
    ref
  ) => {
    // Buttons are set in the display face — a signature Mistral choice.
    const baseClasses = 'rounded-md font-display font-medium transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-mistral-red focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed';

    return (
      <button
        ref={ref}
        className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${fullWidth ? 'w-full' : ''} ${className}`}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading ? (
          <span className="flex items-center justify-center">
            <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-current" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Loading...
          </span>
        ) : (
          children
        )}
      </button>
    );
  }
);

Button.displayName = 'Button';
