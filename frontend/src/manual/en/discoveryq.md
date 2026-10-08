# DiscoveryQ

DiscoveryQ prepares and records field interviews during diagnosis. Pick questions from the question bank, record answers, insights and action items on a session worksheet, and produce Word reports.

> Select a customer first. Sessions and subjects belong to an engagement, so at least one engagement must exist.

## Tabs

| Tab | Contents |
| --- | --- |
| Sessions | Interview and coaching sessions and their worksheets |
| Subjects | Interviewees (name, department, job title, systems they use) |
| Question bank | Standard questions published by LUDA |
| Customer questions | Questions copied for this customer or written from scratch |
| Action items | Follow-ups from all sessions |

## Registering a subject

1. On **Subjects**, choose the engagement and enter name, department, job title and systems.
2. Click **Add subject**.

## Running a session

1. On **Sessions**, click **New session** and enter engagement, subject, title, date and session type (field interview / coaching).
2. Click **Open worksheet** in the list.
3. Choose a question from the bank or customer questions in **Pick questions**, or type one in **Write your own question** and click **Add**.
4. Write the **answer** for each question. It is saved when you leave the field and "Saved" appears.
5. Record findings with **Add insight** and follow-ups with **Add action**. Use **Other insights** for notes not tied to a question.
6. When the interview is over, set the session status to "Done".

## Registering terms from answers

You can send business terms from an answer straight to [OntoMap](/manual/ontomap) as candidates.

1. Select the phrase in the answer. The **Term candidate** field fills in automatically.
2. Click **Register as term**. "Registered as candidate" appears and the term is listed under "Term candidates from this session".
3. Confirm the candidate or merge it into an existing term on OntoMap › Candidates.

## Managing questions

- On **Question bank**, find questions by category and audience and click **Copy to client questions** to make a customer-specific copy.
- On **Customer questions**, write a new question with **New client question** or adapt a copied one.

## Action items

On **Action items**, manage assignee, due date and status (open / in progress / done / cancelled). **Action items CSV** downloads the list.

## Exports and reports

| Button | Where | Result |
| --- | --- | --- |
| Export Markdown | Worksheet | The session as a Markdown file |
| Word report | Worksheet | Session report (.docx): questions and answers, insights, action items, registered terms |
| Discovery report (Word) | Session list | Report covering every session of the engagement (.docx) |
| Action items CSV | Action items tab | The action item list |

Reports are generated on the server and never sent outside. LUDA admins, FDEs and customer admins can export, and every export is recorded in the audit log.
