export const AGENTS = {
  orchestrator: { name: 'Orchestrator',     role: 'Coordinator',          initials: 'OR' },
  scheme:       { name: 'Coverage Agent',   role: 'Schemes & insurance',  initials: 'CV' },
  insurance:    { name: 'Insurance Agent',  role: 'Insurance documents',  initials: 'IN' },
  facility:     { name: 'Facility Agent',   role: 'Places nearby',        initials: 'FA' },
  medicine:     { name: 'Medicine Agent',   role: 'Affordable medicines', initials: 'ME' },
  action:       { name: 'Scheduling Agent', role: 'Calendar scheduling',  initials: 'SA' },
  reminder:     { name: 'Reminder Agent',   role: 'Reminders & tasks',    initials: 'RM' },
  workout:      { name: 'Workout Agent',    role: 'Fitness plans',        initials: 'WO' },
  diet:         { name: 'Diet Agent',       role: 'Nutrition plans',      initials: 'DT' },
  product:      { name: 'Product Agent',    role: 'Price comparison',     initials: 'PR' },
  reader:       { name: 'Reader',           role: 'Your documents',       initials: 'RD' },
};

export const CONNECTORS = [
  { name: 'Google Calendar', initials: 'C' },
  { name: 'Google Drive',    initials: 'D' },
  { name: 'Gmail',           initials: 'M' },
];

export const SUGGESTIONS = [
  { label: 'Find cheaper medicines nearby',       q: 'Where can I get diabetes medicines cheaper near home?' },
  { label: 'Does insurance cover physiotherapy?', q: 'Will insurance cover physiotherapy sessions?' },
  { label: 'Schedule an eye check-up',            q: 'Please schedule an eye check-up' },
];
