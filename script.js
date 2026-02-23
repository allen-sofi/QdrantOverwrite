async function fetchFilenames() {
    const select = document.getElementById('filenameSelect');
    const container = document.getElementById('filenameContainer');

    try {
        const response = await fetch('http://localhost:8000/get_all_filenames');
        const data = await response.json();

        if (response.ok) {
            select.innerHTML = '<option value="">-- Select a file --</option>';
            data.filenames.sort().forEach(name => {
                const opt = document.createElement('option');
                opt.value = name;
                opt.textContent = name;
                select.appendChild(opt);
            });
            container.style.display = 'block';
        } else {
            alert("Error fetching filenames: " + data.detail);
        }
    } catch (err) {
        console.error(err);
        alert("Could not connect to backend.");
    }
}

async function scrollFile() {
    const fileName = document.getElementById('fileNameInput').value;
    const chunkList = document.getElementById('chunkList');

    if (!fileName) {
        alert("Please provide a filename.");
        return;
    }

    chunkList.innerHTML = "⏳ Searching...";

    try {
        const response = await fetch(`http://localhost:8000/scroll?file_name=${encodeURIComponent(fileName)}`, {
            method: 'POST'
        });
        const data = await response.json();

        if (response.ok) {
            chunkList.innerHTML = "";
            if (data.results.length === 0) {
                chunkList.innerHTML = "No chunks found for this file.";
                return;
            }

            data.results.forEach(item => {
                const div = document.createElement('div');
                div.className = 'chunk-item';

                // Store content in a private variable to avoid escaping issues in onclick
                const safeContent = (item.content || '').replace(/'/g, "\\'").replace(/\n/g, '\\n');

                div.innerHTML = `
                    <div class="chunk-id">ID: ${item.id}</div>
                    <div class="chunk-content">${item.content || '[Empty]'}</div>
                    <div class="chunk-actions">
                        <button class="edit-btn">Edit Chunk</button>
                    </div>
                `;

                // Use event listener instead of inline onclick for better safety
                div.querySelector('.edit-btn').addEventListener('click', () => {
                    prepareEdit(item.id, item.content || '');
                });

                chunkList.appendChild(div);
            });
            console.log("Successfully loaded chunks:", data.results.length);
        } else {
            chunkList.innerHTML = "❌ Error: " + data.detail;
        }
    } catch (err) {
        chunkList.innerHTML = "❌ Network error.";
    }
}

function prepareEdit(id, content) {
    document.getElementById('pointId').value = id;
    document.getElementById('newContent').value = content;
    document.getElementById('editCard').scrollIntoView({ behavior: 'smooth' });
}

async function sendOverwrite() {
    const status = document.getElementById('status');
    const pointId = document.getElementById('pointId').value;
    const newContent = document.getElementById('newContent').value;
    const fileName = document.getElementById('fileNameInput').value;

    if (!pointId || !newContent) {
        status.innerText = "❌ ID and Content are required.";
        status.style.color = "#f87171"; // red
        return;
    }

    const payload = {
        point_id: pointId,
        file_name: fileName,
        new_content: newContent,
        action: "overwrite"
    };

    status.innerText = "⏳ Saving changes...";
    status.style.color = "#60a5fa"; // blue

    try {
        const response = await fetch('http://localhost:8000/upsert', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (response.ok) {
            status.innerText = "✅ Successfully updated!";
            status.style.color = "#4ade80"; // green
            // Refresh chunks to show update
            setTimeout(scrollFile, 1500);
        } else {
            status.innerText = "❌ Error: " + (result.detail || "Unknown error");
            status.style.color = "#f87171";
        }
    } catch (error) {
        status.innerText = "❌ Mapped to wrong port or server down?";
        status.style.color = "#f87171";
    }
}