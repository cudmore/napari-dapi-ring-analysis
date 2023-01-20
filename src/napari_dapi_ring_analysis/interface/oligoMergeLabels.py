from napari_tools_menu import register_function

# Jan 2023, I want to have this plugin but add undo/redo

@register_function(menu="Utilities > Manually merge labels (nsbatwm)")
def Manually_merge_labels(labels_layer: "napari.layers.Labels", points_layer: "napari.layers.Points", viewer : "napari.Viewer"):
    if points_layer is None:
        points_layer = viewer.add_points([])
        points_layer.mode = 'ADD'
        return
    labels = np.asarray(labels_layer.data)
    points = points_layer.data

    label_ids = [labels.item(tuple([int(j) for j in i])) for i in points]

    # replace labels with minimum of the selected labels
    new_label_id = min(label_ids)
    for l in label_ids:
        if l != new_label_id:
            labels[labels == l] = new_label_id

    labels_layer.data = labels
    points_layer.data = []
