import React from 'react';

// Catches any render/runtime error in the tree so a single component fault shows a
// friendly recovery screen instead of white-screening the whole app.
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    // Log for debugging; in production this is where you'd report to a monitor.
    console.error('WithCare UI error:', error, info?.componentStack);
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div className="min-h-screen flex items-center justify-center bg-background text-on-surface p-6">
        <div className="max-w-md w-full text-center bg-surface-container-lowest border border-outline-variant rounded-3xl elev-3 p-8">
          <div className="w-14 h-14 rounded-2xl mx-auto mb-4 flex items-center justify-center intelligence-gradient">
            <span className="material-symbols-outlined text-white text-[30px]">sentiment_dissatisfied</span>
          </div>
          <h1 className="font-headline-lg text-[20px] mb-2">Something went wrong</h1>
          <p className="text-[14px] text-on-surface-variant mb-6">
            WithCare hit an unexpected error. Your data is safe — reloading usually fixes it.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="press px-5 py-2.5 rounded-full text-[14px] font-semibold bg-primary text-on-primary hover:opacity-90">
            Reload WithCare
          </button>
        </div>
      </div>
    );
  }
}
