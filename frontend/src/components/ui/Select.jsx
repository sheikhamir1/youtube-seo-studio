import { forwardRef, useId } from 'react';

import { cn } from '../../utils/cn';

/**
 * Native select: keyboard accessible, mobile friendly, and it degrades to a
 * plain list when a native picker is not available.
 */
export const Select = forwardRef(function Select(
  { label, hint, error, options = [], className, id, placeholder, ...rest },
  ref,
) {
  const generatedId = useId();
  const selectId = id || `select-${generatedId}`;
  return (
    <div className="w-full">
      {label && (
        <label htmlFor={selectId} className="mb-1.5 block text-sm font-medium text-content">
          {label}
        </label>
      )}
      <select
        ref={ref}
        id={selectId}
        className={cn('input-base pr-8', error && 'border-danger', className)}
        {...rest}
      >
        {placeholder && <option value="">{placeholder}</option>}
        {options.map((option) => {
          const value = typeof option === 'string' ? option : option.value;
          const optionLabel = typeof option === 'string' ? option : option.label;
          return (
            <option key={value} value={value} disabled={option.disabled}>
              {optionLabel}
            </option>
          );
        })}
      </select>
      {(hint || error) && (
        <p className={cn('mt-1 text-xs', error ? 'text-danger' : 'text-muted')}>{error || hint}</p>
      )}
    </div>
  );
});

export default Select;
