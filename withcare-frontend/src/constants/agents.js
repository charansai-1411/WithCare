export const AGENTS = {
  orchestrator: { name: 'Orchestrator',     role: 'Coordinator',          initials: 'OR' },
  scheme:       { name: 'Scheme Agent',     role: 'Govt health schemes',  initials: 'SC' },
  insurance:    { name: 'Insurance Agent',  role: 'Insurance documents',  initials: 'IN' },
  facility:     { name: 'Facility Agent',   role: 'Hospitals nearby',     initials: 'FA' },
  medicine:     { name: 'Medicine Agent',   role: 'Affordable medicines', initials: 'ME' },
  action:       { name: 'Action Agent',     role: 'Calendar scheduling',  initials: 'AC' },
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
