def test_load_jsons():
    from specter import helpers
    mydict = helpers.load_jsons("./tests/helpers_testdata")
    assert mydict["some_jsonfile"]["blub"] == "bla"
    assert mydict["some_other_jsonfile"]["bla"] == "blub"
    mydict = helpers.load_jsons("./tests/helpers_testdata",'id')
    assert "some_jsonfile" not in mydict
    # instead the value for the key "id" is now used as the top-level key
    assert mydict["ID123"]['blub'] == "bla"
    # This also assumes that the key is unique!!!! 
    assert mydict["ID124"]['bla'] == "blub"
    # ToDo: check the uniqueness in the implementation to avoid issues
    # the filename is added as alias
    assert mydict["ID123"]['alias'] == "some_jsonfile"
    # We also get the fullpath of that file:
    assert mydict["ID123"]['fullpath'] == "./tests/helpers_testdata/some_jsonfile.json"